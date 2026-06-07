import logging
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
import aiohttp
import splunk_sdk
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.connectors.base import BaseConnector, MetricData, LogEntry, Trace

logger = logging.getLogger(__name__)


class SplunkConnector(BaseConnector):
    """Connector for Splunk observability data."""

    def __init__(self):
        super().__init__("splunk")
        self.client = None
        self.session = None

    async def connect(self) -> None:
        """Connect to Splunk."""
        try:
            self.client = splunk_sdk.client.connect(
                host=settings.splunk_host,
                port=settings.splunk_port,
                username=settings.splunk_username,
                password=settings.splunk_password,
                autologin=True,
            )
            self.session = aiohttp.ClientSession()
            logger.info("Connected to Splunk")
        except Exception as e:
            logger.error(f"Failed to connect to Splunk: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Splunk."""
        try:
            if self.session:
                await self.session.close()
            if self.client:
                self.client.logout()
            logger.info("Disconnected from Splunk")
        except Exception as e:
            logger.error(f"Failed to disconnect from Splunk: {e}")

    async def health_check(self) -> bool:
        """Check Splunk health."""
        try:
            response = await self.session.get(
                f"https://{settings.splunk_host}:{settings.splunk_port}/services/server/info",
                auth=aiohttp.BasicAuth(
                    settings.splunk_username, settings.splunk_password
                ),
                ssl=False,
            )
            return response.status == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def query_logs(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> List[LogEntry]:
        """Query logs from Splunk."""
        try:
            start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            kwargs_blockingstatus = {"output_mode": "json"}
            search_query = (
                f"search index={settings.splunk_index} {query} "
                f'earliest="{start_str}" latest="{end_str}" '
                f"| fields - _raw | head {limit}"
            )

            response = self.client.jobs.create(search_query, **kwargs_blockingstatus)

            while not response.is_done():
                await asyncio.sleep(0.1)

            results = response.results

            log_entries = []
            for result in results:
                try:
                    log_entry = LogEntry(
                        timestamp=datetime.fromisoformat(
                            result.get("_time", "").replace("Z", "+00:00")
                        ),
                        message=result.get("message", ""),
                        level=result.get("level", "INFO"),
                        source="splunk",
                        attributes=dict(result),
                    )
                    log_entries.append(log_entry)
                except Exception as e:
                    logger.warning(f"Failed to parse log entry: {e}")

            logger.info(f"Retrieved {len(log_entries)} logs from Splunk")
            return log_entries

        except Exception as e:
            logger.error(f"Failed to query Splunk logs: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def query_metrics(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[MetricData]:
        """Query metrics from Splunk (using metrics data model)."""
        try:
            start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            filter_str = ""
            if filters:
                for key, value in filters.items():
                    filter_str += f' {key}="{value}"'

            kwargs_blockingstatus = {"output_mode": "json"}
            search_query = (
                f"| mstats avg(_value) as value by metric_name where metric_name={metric_name}{filter_str} "
                f'earliest="{start_str}" latest="{end_str}"'
            )

            response = self.client.jobs.create(search_query, **kwargs_blockingstatus)

            while not response.is_done():
                await asyncio.sleep(0.1)

            results = response.results

            metrics = []
            for result in results:
                try:
                    metric = MetricData(
                        timestamp=datetime.fromisoformat(
                            result.get("_time", "").replace("Z", "+00:00")
                        ),
                        metric_name=result.get("metric_name", metric_name),
                        value=float(result.get("value", 0)),
                        tags={},
                        source="splunk",
                    )
                    metrics.append(metric)
                except Exception as e:
                    logger.warning(f"Failed to parse metric: {e}")

            logger.info(f"Retrieved {len(metrics)} metrics from Splunk")
            return metrics

        except Exception as e:
            logger.error(f"Failed to query Splunk metrics: {e}")
            raise

    async def query_traces(
        self,
        service: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> List[Trace]:
        """Query traces from Splunk (requires OpenTelemetry connector)."""
        try:
            start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            kwargs_blockingstatus = {"output_mode": "json"}
            search_query = (
                f'search index="traces" service="{service}" '
                f'earliest="{start_str}" latest="{end_str}" '
                f"| head {limit}"
            )

            response = self.client.jobs.create(search_query, **kwargs_blockingstatus)

            while not response.is_done():
                await asyncio.sleep(0.1)

            results = response.results

            traces = []
            for result in results:
                try:
                    trace = Trace(
                        trace_id=result.get("trace_id", ""),
                        span_id=result.get("span_id", ""),
                        timestamp=datetime.fromisoformat(
                            result.get("_time", "").replace("Z", "+00:00")
                        ),
                        duration_ms=float(result.get("duration_ms", 0)),
                        service=result.get("service", ""),
                        operation=result.get("operation", ""),
                        status=result.get("status", "unknown"),
                        attributes=dict(result),
                    )
                    traces.append(trace)
                except Exception as e:
                    logger.warning(f"Failed to parse trace: {e}")

            logger.info(f"Retrieved {len(traces)} traces from Splunk")
            return traces

        except Exception as e:
            logger.error(f"Failed to query Splunk traces: {e}")
            raise

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.connectors.base import BaseConnector, MetricData, LogEntry, Trace

logger = logging.getLogger(__name__)


class DatadogConnector(BaseConnector):
    """Connector for Datadog observability data."""

    def __init__(self):
        super().__init__("datadog")
        self.client = None
        self.headers = {
            "DD-API-KEY": settings.datadog_api_key,
            "DD-APPLICATION-KEY": settings.datadog_app_key,
        }

    async def connect(self) -> None:
        """Connect to Datadog."""
        try:
            self.client = httpx.AsyncClient(
                base_url=settings.datadog_api_url,
                headers=self.headers,
                timeout=30.0,
            )
            logger.info("Connected to Datadog")
        except Exception as e:
            logger.error(f"Failed to connect to Datadog: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Datadog."""
        try:
            if self.client:
                await self.client.aclose()
            logger.info("Disconnected from Datadog")
        except Exception as e:
            logger.error(f"Failed to disconnect from Datadog: {e}")

    async def health_check(self) -> bool:
        """Check Datadog health."""
        try:
            response = await self.client.get("/api/v1/validate")
            return response.status_code == 200
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
        """Query logs from Datadog."""
        try:
            params = {
                "filter[query]": query,
                "filter[from]": int(start_time.timestamp() * 1000),
                "filter[to]": int(end_time.timestamp() * 1000),
                "page[limit]": limit,
            }

            response = await self.client.get("/api/v2/logs/events", params=params)
            response.raise_for_status()

            data = response.json()
            log_entries = []

            for log in data.get("data", []):
                try:
                    attributes = log.get("attributes", {})
                    log_entry = LogEntry(
                        timestamp=datetime.fromisoformat(
                            attributes.get("timestamp", "").replace("Z", "+00:00")
                        ),
                        message=attributes.get("message", ""),
                        level=attributes.get("level", "INFO"),
                        source="datadog",
                        attributes=attributes,
                    )
                    log_entries.append(log_entry)
                except Exception as e:
                    logger.warning(f"Failed to parse log entry: {e}")

            logger.info(f"Retrieved {len(log_entries)} logs from Datadog")
            return log_entries

        except Exception as e:
            logger.error(f"Failed to query Datadog logs: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def query_metrics(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[MetricData]:
        """Query metrics from Datadog."""
        try:
            query = f"avg:{metric_name}"

            if filters:
                for key, value in filters.items():
                    query += f'{{"{key}":"{value}"}}'

            params = {
                "query": query,
                "from": int(start_time.timestamp()),
                "to": int(end_time.timestamp()),
            }

            response = await self.client.get("/api/v1/query", params=params)
            response.raise_for_status()

            data = response.json()
            metrics = []

            for series in data.get("series", []):
                metric_name_result = series.get("metric", metric_name)
                tags = series.get("tags", {})

                for point in series.get("pointlist", []):
                    try:
                        timestamp_ms, value = point
                        metric = MetricData(
                            timestamp=datetime.utcfromtimestamp(timestamp_ms / 1000),
                            metric_name=metric_name_result,
                            value=float(value),
                            tags=tags,
                            source="datadog",
                        )
                        metrics.append(metric)
                    except Exception as e:
                        logger.warning(f"Failed to parse metric point: {e}")

            logger.info(f"Retrieved {len(metrics)} metrics from Datadog")
            return metrics

        except Exception as e:
            logger.error(f"Failed to query Datadog metrics: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def query_traces(
        self,
        service: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> List[Trace]:
        """Query traces from Datadog."""
        try:
            query = f'service:"{service}"'
            params = {
                "filter[query]": query,
                "filter[from]": int(start_time.timestamp() * 1000),
                "filter[to]": int(end_time.timestamp() * 1000),
                "page[limit]": limit,
            }

            response = await self.client.get("/api/v2/apm/traces", params=params)
            response.raise_for_status()

            data = response.json()
            traces = []

            for trace_data in data.get("data", []):
                try:
                    attributes = trace_data.get("attributes", {})
                    trace = Trace(
                        trace_id=trace_data.get("id", ""),
                        span_id=attributes.get("span_id", ""),
                        timestamp=datetime.fromisoformat(
                            attributes.get("start_time", "").replace("Z", "+00:00")
                        ),
                        duration_ms=float(attributes.get("duration", 0)),
                        service=service,
                        operation=attributes.get("resource", ""),
                        status=attributes.get("status", "ok"),
                        attributes=attributes,
                    )
                    traces.append(trace)
                except Exception as e:
                    logger.warning(f"Failed to parse trace: {e}")

            logger.info(f"Retrieved {len(traces)} traces from Datadog")
            return traces

        except Exception as e:
            logger.error(f"Failed to query Datadog traces: {e}")
            raise

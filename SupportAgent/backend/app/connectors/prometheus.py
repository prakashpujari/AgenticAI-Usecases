import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.connectors.base import BaseConnector, MetricData

logger = logging.getLogger(__name__)


class PrometheusConnector(BaseConnector):
    """Connector for Prometheus metrics."""

    def __init__(self):
        super().__init__("prometheus")
        self.client = None

    async def connect(self) -> None:
        """Connect to Prometheus."""
        try:
            self.client = httpx.AsyncClient(
                base_url=settings.prometheus_url,
                timeout=settings.prometheus_query_timeout,
            )
            logger.info("Connected to Prometheus")
        except Exception as e:
            logger.error(f"Failed to connect to Prometheus: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Prometheus."""
        try:
            if self.client:
                await self.client.aclose()
            logger.info("Disconnected from Prometheus")
        except Exception as e:
            logger.error(f"Failed to disconnect from Prometheus: {e}")

    async def health_check(self) -> bool:
        """Check Prometheus health."""
        try:
            response = await self.client.get("/-/healthy")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def query_metrics(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[MetricData]:
        """Query metrics from Prometheus (range query)."""
        try:
            query = metric_name

            if filters:
                filter_str = ",".join(f'{k}="{v}"' for k, v in filters.items())
                query = f"{metric_name}{{{filter_str}}}"

            params = {
                "query": query,
                "start": int(start_time.timestamp()),
                "end": int(end_time.timestamp()),
                "step": "60s",
            }

            response = await self.client.get("/api/v1/query_range", params=params)
            response.raise_for_status()

            data = response.json()
            metrics = []

            if data.get("status") != "success":
                logger.warning(f"Prometheus query failed: {data.get('error', 'Unknown error')}")
                return metrics

            for result in data.get("data", {}).get("result", []):
                metric_name_result = result.get("metric", {}).get("__name__", metric_name)
                tags = {k: v for k, v in result.get("metric", {}).items() if k != "__name__"}

                for value_point in result.get("values", []):
                    try:
                        timestamp_unix, value = value_point
                        metric = MetricData(
                            timestamp=datetime.utcfromtimestamp(float(timestamp_unix)),
                            metric_name=metric_name_result,
                            value=float(value),
                            tags=tags,
                            source="prometheus",
                        )
                        metrics.append(metric)
                    except Exception as e:
                        logger.warning(f"Failed to parse metric point: {e}")

            logger.info(f"Retrieved {len(metrics)} metrics from Prometheus")
            return metrics

        except Exception as e:
            logger.error(f"Failed to query Prometheus metrics: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def query_instant_metric(
        self,
        metric_name: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Query instant metric from Prometheus."""
        try:
            query = metric_name

            if filters:
                filter_str = ",".join(f'{k}="{v}"' for k, v in filters.items())
                query = f"{metric_name}{{{filter_str}}}"

            params = {"query": query}

            response = await self.client.get("/api/v1/query", params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") != "success":
                logger.warning(f"Prometheus query failed: {data.get('error', 'Unknown error')}")
                return 0.0

            result = data.get("data", {}).get("result", [])
            if result:
                value = result[0].get("value", ["", "0"])[1]
                return float(value)

            return 0.0

        except Exception as e:
            logger.error(f"Failed to query Prometheus instant metric: {e}")
            raise

    async def query_logs(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> List[Any]:
        """Prometheus doesn't have native log querying. Return empty list."""
        logger.info("Prometheus connector does not support log queries")
        return []

    async def query_traces(
        self,
        service: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> List[Any]:
        """Prometheus doesn't have native trace querying. Return empty list."""
        logger.info("Prometheus connector does not support trace queries")
        return []

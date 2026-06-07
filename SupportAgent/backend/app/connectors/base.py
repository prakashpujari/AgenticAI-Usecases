from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class MetricData:
    timestamp: datetime
    metric_name: str
    value: float
    tags: Dict[str, str]
    source: str


@dataclass
class LogEntry:
    timestamp: datetime
    message: str
    level: str  # ERROR, WARN, INFO, DEBUG
    source: str
    attributes: Dict[str, Any]


@dataclass
class Trace:
    trace_id: str
    span_id: str
    timestamp: datetime
    duration_ms: float
    service: str
    operation: str
    status: str  # ok, error, unknown
    attributes: Dict[str, Any]


class BaseConnector(ABC):
    """Base class for all observability connectors."""

    def __init__(self, source_name: str):
        self.source_name = source_name

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the observability tool."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the observability tool."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the connector is healthy."""
        pass

    @abstractmethod
    async def query_metrics(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[MetricData]:
        """Query metrics from the source."""
        pass

    @abstractmethod
    async def query_logs(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> List[LogEntry]:
        """Query logs from the source."""
        pass

    @abstractmethod
    async def query_traces(
        self,
        service: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> List[Trace]:
        """Query traces from the source."""
        pass

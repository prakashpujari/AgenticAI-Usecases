import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from app.connectors.splunk import SplunkConnector
from app.connectors.datadog import DatadogConnector
from app.connectors.prometheus import PrometheusConnector
from app.ml.anomaly_detection import HybridAnomalyDetector
import numpy as np

logger = logging.getLogger(__name__)


KNOWN_FAILURE_PATTERNS = {
    "timeout": {
        "keywords": [
            "timeout",
            "timed out",
            "ReadTimeout",
            "SocketTimeout",
            "ConnectionTimeout",
        ],
        "severity": "P2",
        "pattern_type": "timeout_error",
    },
    "service_unavailable": {
        "keywords": ["503", "Service Unavailable", "Bad Gateway", "504"],
        "severity": "P1",
        "pattern_type": "availability_error",
    },
    "database_error": {
        "keywords": [
            "connection refused",
            "database down",
            "db unreachable",
            "sql error",
        ],
        "severity": "P1",
        "pattern_type": "database_error",
    },
    "pod_crash": {
        "keywords": ["CrashLoopBackOff", "pod restart", "crash loop"],
        "severity": "P2",
        "pattern_type": "infrastructure_error",
    },
    "high_latency": {
        "keywords": ["latency", "slow", "p99", "response time"],
        "severity": "P2",
        "pattern_type": "performance_error",
    },
    "memory_leak": {
        "keywords": ["memory leak", "OOM", "out of memory", "memory growth"],
        "severity": "P2",
        "pattern_type": "resource_error",
    },
    "kafka_lag": {
        "keywords": ["kafka lag", "consumer lag", "topic unavailable"],
        "severity": "P2",
        "pattern_type": "queue_error",
    },
    "auth_failure": {
        "keywords": ["auth failure", "unauthorized", "401", "forbidden", "403"],
        "severity": "P2",
        "pattern_type": "security_error",
    },
}


class IncidentDetectionAgent:
    """Agent for detecting incidents from observability data."""

    def __init__(self):
        self.splunk = SplunkConnector()
        self.datadog = DatadogConnector()
        self.prometheus = PrometheusConnector()
        self.anomaly_detector = None

    async def initialize(self) -> None:
        """Initialize connectors."""
        try:
            await self.splunk.connect()
            await self.datadog.connect()
            await self.prometheus.connect()
            logger.info("Detection agent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize detection agent: {e}")
            raise

    async def cleanup(self) -> None:
        """Cleanup connectors."""
        try:
            await self.splunk.disconnect()
            await self.datadog.disconnect()
            await self.prometheus.disconnect()
            logger.info("Detection agent cleaned up")
        except Exception as e:
            logger.error(f"Failed to cleanup detection agent: {e}")

    def _check_known_patterns(self, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check logs against known failure patterns."""
        detected_patterns = []

        for log in logs:
            message = log.get("message", "").lower()

            for pattern_name, pattern_config in KNOWN_FAILURE_PATTERNS.items():
                for keyword in pattern_config["keywords"]:
                    if keyword.lower() in message:
                        detected_patterns.append(
                            {
                                "pattern": pattern_name,
                                "type": pattern_config["pattern_type"],
                                "severity": pattern_config["severity"],
                                "confidence": 0.85,
                                "source_log": log,
                            }
                        )
                        break

        return detected_patterns

    def _extract_features_from_logs(self, logs: List[Dict[str, Any]]) -> np.ndarray:
        """Extract numeric features from logs for ML anomaly detection."""
        features = []

        for log in logs:
            feature_vector = []

            # Count error levels
            message = log.get("message", "")
            level = log.get("level", "INFO").upper()

            feature_vector.append(1 if level == "ERROR" else 0)
            feature_vector.append(1 if level == "WARN" else 0)
            feature_vector.append(len(message.split()))  # Message length
            feature_vector.append(
                1 if any(kw in message.lower() for kw in ["error", "fail", "exception"])
                else 0
            )

            features.append(feature_vector)

        return np.array(features) if features else np.zeros((1, 4))

    async def detect_from_logs(
        self,
        query: str = '*level="ERROR"',
        lookback_hours: int = 1,
    ) -> Dict[str, Any]:
        """Detect incidents from logs."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=lookback_hours)

            splunk_logs = await self.splunk.query_logs(query, start_time, end_time)
            datadog_logs = await self.datadog.query_logs(query, start_time, end_time)

            all_logs = [log.__dict__ for log in splunk_logs] + [log.__dict__ for log in datadog_logs]

            # Check known patterns
            patterns = self._check_known_patterns(all_logs)

            # Check ML anomalies
            if self.anomaly_detector and len(all_logs) > 10:
                features = self._extract_features_from_logs(all_logs)
                ml_preds, ml_scores = self.anomaly_detector.predict(features)

                anomaly_count = np.sum(ml_preds == -1)
                anomaly_rate = anomaly_count / len(ml_preds) if len(ml_preds) > 0 else 0

                return {
                    "incident_detected": len(patterns) > 0 or anomaly_rate > 0.1,
                    "patterns": patterns,
                    "anomaly_rate": float(anomaly_rate),
                    "anomaly_count": int(anomaly_count),
                    "total_logs": len(all_logs),
                    "ml_max_score": float(ml_scores.max()) if len(ml_scores) > 0 else 0,
                    "confidence_score": max(
                        max([p["confidence"] for p in patterns], default=0),
                        anomaly_rate,
                    ),
                }

            return {
                "incident_detected": len(patterns) > 0,
                "patterns": patterns,
                "anomaly_rate": 0.0,
                "anomaly_count": 0,
                "total_logs": len(all_logs),
                "ml_max_score": 0,
                "confidence_score": max([p["confidence"] for p in patterns], default=0),
            }

        except Exception as e:
            logger.error(f"Failed to detect from logs: {e}")
            return {
                "incident_detected": False,
                "error": str(e),
                "patterns": [],
                "confidence_score": 0,
            }

    async def detect_from_metrics(
        self,
        metrics: List[str] = None,
        lookback_hours: int = 1,
    ) -> Dict[str, Any]:
        """Detect incidents from metrics (spikes, anomalies)."""
        try:
            if metrics is None:
                metrics = [
                    "cpu_usage",
                    "memory_usage",
                    "error_rate",
                    "latency_p99",
                    "request_rate",
                ]

            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=lookback_hours)

            all_metrics_data = []

            for metric in metrics:
                try:
                    prom_metrics = await self.prometheus.query_metrics(
                        metric, start_time, end_time
                    )
                    all_metrics_data.extend([m.__dict__ for m in prom_metrics])
                except Exception as e:
                    logger.warning(f"Failed to query {metric} from Prometheus: {e}")

            if not all_metrics_data:
                return {
                    "incident_detected": False,
                    "metrics_analyzed": 0,
                    "anomalies": [],
                    "confidence_score": 0,
                }

            # Extract values for ML anomaly detection
            values = np.array([m["value"] for m in all_metrics_data]).reshape(-1, 1)

            if self.anomaly_detector and len(values) > 10:
                ml_preds, ml_scores = self.anomaly_detector.predict(values)

                anomalies = [
                    {
                        "metric": all_metrics_data[i]["metric_name"],
                        "value": float(all_metrics_data[i]["value"]),
                        "timestamp": str(all_metrics_data[i]["timestamp"]),
                        "anomaly_score": float(ml_scores[i]),
                    }
                    for i in range(len(ml_preds))
                    if ml_preds[i] == -1
                ]

                return {
                    "incident_detected": len(anomalies) > 0,
                    "metrics_analyzed": len(all_metrics_data),
                    "anomalies": anomalies[:10],  # Top 10
                    "anomaly_rate": float(np.sum(ml_preds == -1) / len(ml_preds)),
                    "confidence_score": float(ml_scores.max()) if len(ml_scores) > 0 else 0,
                }

            return {
                "incident_detected": False,
                "metrics_analyzed": len(all_metrics_data),
                "anomalies": [],
                "confidence_score": 0,
            }

        except Exception as e:
            logger.error(f"Failed to detect from metrics: {e}")
            return {
                "incident_detected": False,
                "error": str(e),
                "anomalies": [],
                "confidence_score": 0,
            }

    async def detect_incidents(
        self,
        check_logs: bool = True,
        check_metrics: bool = True,
        lookback_hours: int = 1,
    ) -> Dict[str, Any]:
        """Main detection method - checks both logs and metrics."""
        try:
            results = {
                "incident_id": str(uuid.uuid4()),
                "detected_at": datetime.utcnow().isoformat(),
                "incident_detected": False,
                "checks": {},
            }

            if check_logs:
                log_result = await self.detect_from_logs(lookback_hours=lookback_hours)
                results["checks"]["logs"] = log_result
                results["incident_detected"] |= log_result.get("incident_detected", False)

            if check_metrics:
                metric_result = await self.detect_from_metrics(lookback_hours=lookback_hours)
                results["checks"]["metrics"] = metric_result
                results["incident_detected"] |= metric_result.get("incident_detected", False)

            # Calculate overall confidence
            confidences = [
                results["checks"][check].get("confidence_score", 0)
                for check in results["checks"]
            ]
            results["overall_confidence_score"] = max(confidences, default=0)

            return results

        except Exception as e:
            logger.error(f"Failed to detect incidents: {e}")
            return {
                "incident_detected": False,
                "error": str(e),
                "confidence_score": 0,
            }

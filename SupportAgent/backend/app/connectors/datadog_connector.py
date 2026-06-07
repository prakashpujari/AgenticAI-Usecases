"""
Datadog Connector - Pull metrics, logs, and traces for incident detection
"""

import os
import logging
from typing import Optional, List, Dict
import httpx
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class DatadogConnector:
    """Connector to integrate with Datadog for monitoring and alerting"""

    def __init__(self):
        self.api_key = os.getenv("DATADOG_API_KEY", "")
        self.app_key = os.getenv("DATADOG_APP_KEY", "")
        self.api_url = os.getenv("DATADOG_API_URL", "https://api.datadoghq.com")
        self.enabled = bool(self.api_key and self.app_key)

        if self.enabled:
            logger.info(f"Datadog connector initialized: {self.api_url}")
            self.headers = {
                "DD-API-KEY": self.api_key,
                "DD-APPLICATION-KEY": self.app_key,
                "Content-Type": "application/json"
            }
        else:
            logger.warning("Datadog connector disabled: Missing API keys")

    async def get_metrics(
        self,
        query: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Optional[Dict]:
        """Query Datadog metrics"""
        if not self.enabled:
            return None

        try:
            if not start_time:
                start_time = int((datetime.utcnow() - timedelta(hours=1)).timestamp())
            if not end_time:
                end_time = int(datetime.utcnow().timestamp())

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/api/v1/query",
                    params={
                        "query": query,
                        "from": start_time,
                        "to": end_time
                    },
                    headers=self.headers,
                    timeout=30.0
                )

                if response.status_code == 200:
                    logger.info(f"Retrieved metrics: {query}")
                    return response.json()
                else:
                    logger.error(f"Datadog metrics error: {response.status_code}")
                    return None

        except Exception as error:
            logger.error(f"Error querying metrics: {str(error)}")
            return None

    async def get_logs(
        self,
        query: str,
        limit: int = 100
    ) -> Optional[List[Dict]]:
        """Query Datadog logs"""
        if not self.enabled:
            return None

        try:
            start_time = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
            end_time = datetime.utcnow().isoformat() + "Z"

            payload = {
                "filter": {
                    "query": query,
                    "from": start_time,
                    "to": end_time
                },
                "page": {"limit": limit}
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/api/v2/logs/events/search",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    logs = data.get("data", [])
                    logger.info(f"Retrieved {len(logs)} logs")
                    return logs
                else:
                    return None

        except Exception as error:
            logger.error(f"Error querying logs: {str(error)}")
            return None

    async def health_check(self) -> Dict:
        """Check Datadog connector health"""
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "Datadog connector not configured"
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/api/v1/validate_credentials",
                    headers=self.headers,
                    timeout=10.0
                )

                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "api_url": self.api_url,
                        "message": "Connected to Datadog"
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}",
                        "api_url": self.api_url
                    }

        except Exception as error:
            return {
                "status": "error",
                "error": str(error),
                "api_url": self.api_url
            }

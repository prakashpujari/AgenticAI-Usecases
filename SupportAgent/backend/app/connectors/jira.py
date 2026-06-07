"""
Jira Connector - Create and manage incidents in Jira
"""

import os
import logging
import base64
from typing import Optional, Dict, List
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)


class JiraConnector:
    """Connector to integrate with Jira Cloud"""

    def __init__(self):
        self.server = os.getenv("JIRA_SERVER", "https://mailtopprakash01.atlassian.net")
        self.username = os.getenv("JIRA_USERNAME", "mailtopprakash01@gmail.com")
        self.api_token = os.getenv("JIRA_API_TOKEN", "")
        self.project_key = os.getenv("JIRA_PROJECT_KEY", "OPS")
        self.enabled = bool(self.api_token)

        if self.enabled:
            # Create auth header
            auth_string = f"{self.username}:{self.api_token}"
            auth_bytes = auth_string.encode('utf-8')
            auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
            self.auth_header = f"Basic {auth_b64}"
            logger.info(f"Jira connector initialized: {self.server}")
        else:
            logger.warning("Jira connector disabled: No API token configured")

    async def create_incident_ticket(
        self,
        title: str,
        description: str,
        severity: str = "Medium",
        affected_services: List[str] = None,
        incident_id: str = None
    ) -> Optional[Dict]:
        """
        Create a Jira ticket for an incident

        Args:
            title: Incident title
            description: Incident description
            severity: Incident severity (Critical, High, Medium, Low)
            affected_services: List of affected services
            incident_id: Internal incident ID for linking

        Returns:
            Jira ticket details including key and URL
        """

        if not self.enabled:
            logger.warning("Jira connector disabled, skipping ticket creation")
            return None

        try:
            # Map severity levels
            severity_map = {
                "P1_CRITICAL": "Highest",
                "P2_HIGH": "High",
                "P3_MEDIUM": "Medium",
                "P4_LOW": "Low"
            }
            jira_priority = severity_map.get(severity, "High")

            # Build description with services
            full_description = description
            if affected_services:
                full_description += f"\n\nAffected Services: {', '.join(affected_services)}"
            if incident_id:
                full_description += f"\n\nInternal Incident ID: {incident_id}"
            full_description += f"\n\nCreated: {datetime.utcnow().isoformat()}"

            # Prepare issue payload
            payload = {
                "fields": {
                    "project": {
                        "key": self.project_key
                    },
                    "summary": title,
                    "description": full_description,
                    "issuetype": {
                        "name": "Incident"
                    },
                    "priority": {
                        "name": jira_priority
                    },
                    "labels": ["aiops", "automated", severity.lower()],
                    "customfield_10000": incident_id or "N/A"
                }
            }

            # Create the issue
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.server}/rest/api/3/issues",
                    json=payload,
                    headers={
                        "Authorization": self.auth_header,
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code in (200, 201):
                    result = response.json()
                    ticket_key = result.get("key")
                    ticket_id = result.get("id")

                    logger.info(f"Created Jira ticket: {ticket_key}")

                    return {
                        "ticket_key": ticket_key,
                        "ticket_id": ticket_id,
                        "ticket_url": f"{self.server}/browse/{ticket_key}",
                        "status": "created",
                        "created_at": datetime.utcnow().isoformat()
                    }
                else:
                    logger.error(f"Jira API error: {response.status_code} - {response.text}")
                    return {
                        "status": "error",
                        "error": response.text,
                        "http_status": response.status_code
                    }

        except Exception as error:
            logger.error(f"Error creating Jira ticket: {str(error)}")
            return {
                "status": "error",
                "error": str(error)
            }

    async def get_ticket(self, ticket_key: str) -> Optional[Dict]:
        """Get ticket details"""
        if not self.enabled:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.server}/rest/api/3/issues/{ticket_key}",
                    headers={
                        "Authorization": self.auth_header,
                        "Accept": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Error fetching ticket {ticket_key}: {response.status_code}")
                    return None

        except Exception as error:
            logger.error(f"Error fetching Jira ticket: {str(error)}")
            return None

    async def update_ticket(
        self,
        ticket_key: str,
        status: str = None,
        comment: str = None,
        fields: Dict = None
    ) -> bool:
        """Update ticket status or add comment"""
        if not self.enabled:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Add comment if provided
                if comment:
                    await client.post(
                        f"{self.server}/rest/api/3/issues/{ticket_key}/comments",
                        json={"body": {"content": [{"type": "text", "text": comment}]}},
                        headers={
                            "Authorization": self.auth_header,
                            "Content-Type": "application/json"
                        },
                        timeout=10.0
                    )

                # Update status if provided
                if status:
                    # Get available transitions
                    transitions_response = await client.get(
                        f"{self.server}/rest/api/3/issues/{ticket_key}/transitions",
                        headers={
                            "Authorization": self.auth_header,
                            "Accept": "application/json"
                        },
                        timeout=10.0
                    )

                    if transitions_response.status_code == 200:
                        transitions = transitions_response.json().get("transitions", [])
                        transition_id = None

                        for t in transitions:
                            if t.get("name", "").lower() == status.lower():
                                transition_id = t.get("id")
                                break

                        if transition_id:
                            await client.post(
                                f"{self.server}/rest/api/3/issues/{ticket_key}/transitions",
                                json={"transition": {"id": transition_id}},
                                headers={
                                    "Authorization": self.auth_header,
                                    "Content-Type": "application/json"
                                },
                                timeout=10.0
                            )

                # Update custom fields if provided
                if fields:
                    await client.put(
                        f"{self.server}/rest/api/3/issues/{ticket_key}",
                        json={"fields": fields},
                        headers={
                            "Authorization": self.auth_header,
                            "Content-Type": "application/json"
                        },
                        timeout=10.0
                    )

            return True

        except Exception as error:
            logger.error(f"Error updating Jira ticket: {str(error)}")
            return False

    async def search_tickets(self, query: str) -> Optional[List[Dict]]:
        """Search for tickets using JQL"""
        if not self.enabled:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.server}/rest/api/3/search",
                    params={"jql": query},
                    headers={
                        "Authorization": self.auth_header,
                        "Accept": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    return response.json().get("issues", [])
                else:
                    logger.error(f"Jira search error: {response.status_code}")
                    return None

        except Exception as error:
            logger.error(f"Error searching Jira: {str(error)}")
            return None

    async def health_check(self) -> Dict:
        """Check Jira connector health"""
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "Jira connector not configured"
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.server}/rest/api/3/myself",
                    headers={
                        "Authorization": self.auth_header,
                        "Accept": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    user_info = response.json()
                    return {
                        "status": "healthy",
                        "server": self.server,
                        "user": user_info.get("displayName"),
                        "email": user_info.get("emailAddress"),
                        "project": self.project_key
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}",
                        "server": self.server
                    }

        except Exception as error:
            return {
                "status": "error",
                "error": str(error),
                "server": self.server
            }

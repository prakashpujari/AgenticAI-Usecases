"""
Jira Cloud REST API v3 client.
Creates issues, fetches issues, and provides a health-check endpoint.
"""
from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

# Priority mapping from internal P0–P3 to Jira display names
_PRIORITY_MAP: Dict[str, str] = {
    "P0": "Highest",
    "P1": "High",
    "P2": "Medium",
    "P3": "Low",
}


def _build_adf_doc(text: str) -> Dict[str, Any]:
    """Wrap plain text in a minimal Atlassian Document Format document."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


class JiraService:
    """Async Jira Cloud REST API v3 client."""

    def __init__(self) -> None:
        # Jira Cloud REST API uses HTTP Basic Auth encoded as base64.
        # The credentials are built once at startup rather than per-request
        # to avoid repeated string encoding overhead.
        credentials = base64.b64encode(
            f"{settings.jira_email}:{settings.jira_api_token}".encode()
        ).decode()
        self._base_url = settings.jira_base_url.rstrip("/")
        self._headers: Dict[str, str] = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Issue creation
    # ------------------------------------------------------------------

    def _build_description(self, ticket: Dict[str, Any]) -> str:
        """Compose a full description string from ticket fields."""
        parts = [ticket.get("description", "")]

        ac_list: List[Dict] = ticket.get("acceptance_criteria", [])
        if ac_list:
            ac_lines = ["", "**Acceptance Criteria:**"]
            for ac in ac_list:
                ac_lines.append(f"Scenario: {ac.get('scenario', '')}")
                ac_lines.append(f"  Given {ac.get('given', '')}")
                ac_lines.append(f"  When  {ac.get('when', '')}")
                ac_lines.append(f"  Then  {ac.get('then', '')}")
            parts.append("\n".join(ac_lines))

        assumptions: List[str] = ticket.get("assumptions", [])
        if assumptions:
            parts.append(
                "\n**Assumptions:**\n" + "\n".join(f"- {a}" for a in assumptions)
            )

        open_qs: List[str] = ticket.get("open_questions", [])
        if open_qs:
            parts.append(
                "\n**Open Questions:**\n" + "\n".join(f"- {q}" for q in open_qs)
            )

        sources: List[str] = ticket.get("source_references", [])
        if sources:
            parts.append(
                "\n**Source References:**\n" + "\n".join(f"- {s}" for s in sources)
            )

        return "\n".join(parts)

    async def create_issue(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Create a single Jira issue. Returns key, type, title, URL."""
        issue_type: str = ticket.get("issue_type", "Story")
        jira_priority = _PRIORITY_MAP.get(ticket.get("priority", "P2"), "Medium")
        project_key = ticket.get("project_key", settings.jira_default_project)
        description_text = self._build_description(ticket)

        # Jira REST v3 requires the description in Atlassian Document Format (ADF)
        # rather than plain text or markdown. _build_adf_doc wraps the text in
        # the minimal valid ADF structure.
        payload: Dict[str, Any] = {
            "fields": {
                "project": {"key": project_key},
                "summary": ticket.get("title", "")[:255],  # Jira enforces 255-char limit
                "description": _build_adf_doc(description_text),
                "issuetype": {"name": issue_type},
                "priority": {"name": jira_priority},
                "labels": ticket.get("labels", []),
            }
        }

        # Epic link for non-Epic types
        linked_epic: Optional[str] = ticket.get("linked_epic_key")
        if linked_epic and issue_type != "Epic":
            # Jira Next-gen projects use "parent"; classic projects use
            # the "Epic Link" custom field (customfield_10014). We write
            # to customfield_10014 here; adjust for your Jira configuration.
            payload["fields"]["customfield_10014"] = linked_epic

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/rest/api/3/issue",
                headers=self._headers,
                json=payload,
            )

        if response.status_code in (200, 201):
            data = response.json()
            return {
                "jira_key": data["key"],
                "issue_type": issue_type,
                "title": ticket.get("title", ""),
                "url": f"{self._base_url}/browse/{data['key']}",
            }

        logger.error(
            "Jira create_issue failed: %s — %s",
            response.status_code,
            response.text[:300],
        )
        raise RuntimeError(
            f"Jira API error {response.status_code}: {response.text[:200]}"
        )

    # ------------------------------------------------------------------
    # Issue retrieval
    # ------------------------------------------------------------------

    async def get_issue(self, jira_key: str) -> Optional[Dict[str, Any]]:
        """Fetch a Jira issue by key; returns None if not found."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._base_url}/rest/api/3/issue/{jira_key}",
                headers=self._headers,
            )
        if response.status_code == 200:
            return response.json()
        if response.status_code == 404:
            return None
        raise RuntimeError(
            f"Jira API error {response.status_code}: {response.text[:200]}"
        )

    # ------------------------------------------------------------------
    # Recent tickets
    # ------------------------------------------------------------------

    async def get_recent_tickets(
        self,
        project_keys: list[str],
        limit: int = 5,
    ) -> list[dict]:
        """
        Fetch the most recently created tickets across the given projects.
        Uses JQL: project in (...) ORDER BY created DESC.
        Returns a simplified list of dicts safe to send to the frontend.
        """
        if not project_keys:
            return []

        projects_jql = ",".join(project_keys)
        jql = f"project in ({projects_jql}) ORDER BY created DESC"
        params = {
            "jql": jql,
            "maxResults": limit,
            "fields": "summary,status,issuetype,priority,assignee,created,labels",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self._base_url}/rest/api/3/search/jql",
                    headers=self._headers,
                    params=params,
                )
        except Exception as exc:
            logger.error("Jira get_recent_tickets request failed: %s", exc)
            return []

        if response.status_code != 200:
            logger.error(
                "Jira get_recent_tickets failed: %s — %s",
                response.status_code,
                response.text[:200],
            )
            return []

        issues = response.json().get("issues", [])
        result: list[dict] = []
        for issue in issues:
            fields = issue.get("fields", {})
            priority_raw = (fields.get("priority") or {}).get("name", "")
            # Map Jira priority names back to P0-P3 for consistent UI display
            _REVERSE_PRIORITY = {
                "Highest": "P0", "High": "P1", "Medium": "P2",
                "Low": "P3", "Lowest": "P3",
            }
            result.append({
                "jira_key": issue.get("key"),
                "title": fields.get("summary", ""),
                "issue_type": (fields.get("issuetype") or {}).get("name", ""),
                "status": (fields.get("status") or {}).get("name", ""),
                "priority": _REVERSE_PRIORITY.get(priority_raw, priority_raw),
                "assignee": (
                    (fields.get("assignee") or {}).get("displayName")
                ),
                "labels": fields.get("labels", []),
                "created": fields.get("created", ""),
                "url": f"{self._base_url}/browse/{issue.get('key')}",
            })
        return result

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._base_url}/rest/api/3/myself",
                    headers=self._headers,
                )
            return response.status_code == 200
        except Exception as exc:
            logger.error("Jira health check failed: %s", exc)
            return False


# Module-level singleton
jira_service = JiraService()

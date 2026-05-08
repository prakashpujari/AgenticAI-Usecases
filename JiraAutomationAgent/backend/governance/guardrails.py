"""
Guardrails: JSON parsing, schema validation, and field-level checks
for all ticket drafts before they reach the Jira Writer.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, List, Optional, Union

from ..config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid enum values (derived from settings so they stay in sync)
# ---------------------------------------------------------------------------
VALID_ISSUE_TYPES: set[str] = set(settings.allowed_issue_types)
VALID_PRIORITIES: set[str] = set(settings.allowed_priorities)
_JIRA_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
_MARKDOWN_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class GuardrailViolation(Exception):
    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__(f"Guardrail violations: {violations}")


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def safe_parse_json(text: str) -> Optional[Union[dict, list]]:
    """
    Parse JSON from an LLM response that may be wrapped in markdown code fences.
    Returns None on failure instead of raising.
    """
    if not text:
        return None

    text = text.strip()

    # Even with response_format={"type": "json_object"}, some older OpenAI
    # model versions occasionally wrap output in triple-backtick fences.
    # This regex strips ``` json ``` or plain ``` delimiters before parsing.
    text = _MARKDOWN_CODE_FENCE_RE.sub("", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error: %s | snippet: %.200s", exc, text)
        return None


# ---------------------------------------------------------------------------
# Ticket-level validation
# ---------------------------------------------------------------------------

def validate_ticket_draft(draft: dict) -> list[str]:
    """Validate a single ticket draft. Returns a list of violation messages."""
    violations: list[str] = []

    # Issue type
    issue_type = draft.get("issue_type", "")
    if issue_type not in VALID_ISSUE_TYPES:
        violations.append(
            f"Invalid issue_type '{issue_type}'. Must be one of {sorted(VALID_ISSUE_TYPES)}"
        )

    # Priority
    priority = draft.get("priority", "")
    if priority not in VALID_PRIORITIES:
        violations.append(
            f"Invalid priority '{priority}'. Must be one of {sorted(VALID_PRIORITIES)}"
        )

    # Title length
    title = draft.get("title", "")
    if not title or len(title.strip()) < 5:
        violations.append("Title must be at least 5 characters")
    if len(title) > 255:
        violations.append("Title must not exceed 255 characters")

    # Description
    if not draft.get("description", "").strip():
        violations.append("Description is required")

    # Project key
    project_key = draft.get("project_key", "")
    if project_key not in settings.allowed_projects:
        violations.append(
            f"Project key '{project_key}' is not in allowed projects "
            f"{settings.allowed_projects}"
        )

    # Linked epic key — must be a real Jira key format if provided
    linked_epic = draft.get("linked_epic_key") or ""
    if linked_epic and not _JIRA_KEY_RE.match(linked_epic):
        # Prevent the LLM from hallucinating keys like "PROJ-ABC" or
        # free-text strings that would cause a 400 on the Jira API.
        violations.append(
            f"linked_epic_key '{linked_epic}' is not a valid Jira key format (e.g. PROJ-123)"
        )

    # Acceptance criteria structure — LLM may return plain strings or dicts
    for i, ac in enumerate(draft.get("acceptance_criteria", [])):
        if isinstance(ac, str):
            # Plain-string AC is acceptable; nothing structural to validate
            if not ac.strip():
                violations.append(
                    f"acceptance_criteria[{i}] must not be an empty string"
                )
            continue
        for field in ("scenario", "given", "when", "then"):
            if not ac.get(field, "").strip():
                violations.append(
                    f"acceptance_criteria[{i}].{field} must not be empty"
                )

    return violations


def validate_tickets(drafts: list[dict]) -> list[str]:
    """Validate all drafts; returns aggregated violations with ticket indices."""
    all_violations: list[str] = []
    for i, draft in enumerate(drafts):
        for v in validate_ticket_draft(draft):
            all_violations.append(f"Ticket[{i}]: {v}")
    return all_violations


def validate_review_result(result: dict) -> list[str]:
    """Validate a reviewer agent output."""
    violations: list[str] = []
    if result.get("status") not in ("APPROVED", "CHANGES_REQUIRED"):
        violations.append(f"Invalid review status: '{result.get('status')}'")
    if not result.get("feedback", "").strip():
        violations.append("Review feedback is required")
    return violations

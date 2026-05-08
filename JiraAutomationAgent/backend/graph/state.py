"""
LangGraph agent state definition.
Every graph node reads and writes into this typed dict.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class JiraAgentState(TypedDict, total=False):
    # ── Input ─────────────────────────────────────────────────────────
    raw_input: str
    jira_key: Optional[str]
    mode: str              # "create" | "review" | "coach"

    # ── RBAC ──────────────────────────────────────────────────────────
    allowed_projects: List[str]
    allowed_components: List[str]
    user_role: str
    user_id: str

    # ── Pre-processing ────────────────────────────────────────────────
    normalized_input: str
    redacted_input: str
    pii_detected: List[Dict[str, Any]]
    rbac_violations: List[str]
    rbac_context: str

    # ── Deduplication ─────────────────────────────────────────────────
    dedupe_matches: List[Dict[str, Any]]

    # ── RAG ───────────────────────────────────────────────────────────
    retrieved_context: List[Dict[str, Any]]
    formatted_context: str

    # ── Agent outputs ─────────────────────────────────────────────────
    ticket_drafts: List[Dict[str, Any]]
    review_result: Dict[str, Any]        # { status, feedback }
    explainer_output: Dict[str, Any]     # { principles, applied_to_this_ticket }

    # ── Validation ────────────────────────────────────────────────────
    validation_errors: List[str]
    is_valid: bool

    # ── Jira ──────────────────────────────────────────────────────────
    create_in_jira: bool
    created_issues: List[Dict[str, Any]]

    # ── Control flow ──────────────────────────────────────────────────
    iteration_count: int
    max_iterations: int

    # ── Meta ──────────────────────────────────────────────────────────
    error: Optional[str]
    trace_id: Optional[str]

"""
FastAPI request / response schemas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreateTicketRequest(BaseModel):
    raw_input: str = Field(..., min_length=10, description="Unstructured input text")
    user_id: str = Field(..., description="Caller user ID for RBAC audit")
    allowed_projects: List[str] = Field(..., description="Projects this user may access")
    allowed_components: List[str] = Field(default_factory=list)
    user_role: str = Field("product_owner", description="Caller role")
    context_hints: Optional[str] = Field(None, description="Optional extra context")
    create_in_jira: bool = Field(False, description="If true, persist approved ticket(s) to Jira")


class ReviewTicketRequest(BaseModel):
    jira_key: Optional[str] = Field(None, description="Existing Jira issue key to review")
    ticket_content: Optional[str] = Field(
        None, description="Raw ticket content to review (alternative to jira_key)"
    )
    user_id: str
    allowed_projects: List[str]
    user_role: str = "product_owner"


class TicketResponse(BaseModel):
    ticket_drafts: List[Dict[str, Any]] = Field(default_factory=list)
    ai_review: Optional[Dict[str, Any]] = None
    how_to_create_explainer: Optional[Dict[str, Any]] = None
    created_issues: List[Dict[str, Any]] = Field(default_factory=list)
    dedupe_matches: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_context: List[Dict[str, Any]] = Field(default_factory=list)
    trace_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    services: Dict[str, str]


class RecentTicket(BaseModel):
    jira_key: str
    title: str
    issue_type: str
    status: str
    priority: str
    assignee: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    created: str
    url: str


class RecentTicketsResponse(BaseModel):
    tickets: List[RecentTicket] = Field(default_factory=list)

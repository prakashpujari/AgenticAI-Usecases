"""
Pydantic models for Jira ticket drafts and agent outputs.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class IssueType(str, Enum):
    EPIC = "Epic"
    STORY = "Story"
    BUG = "Bug"
    TASK = "Task"
    SUBTASK = "Sub-task"


class AcceptanceCriteria(BaseModel):
    scenario: str = Field(..., description="Scenario name")
    given: str = Field(..., description="Given (precondition)")
    when: str = Field(..., description="When (action)")
    then: str = Field(..., description="Then (expected outcome)")


class TicketDraft(BaseModel):
    issue_type: IssueType
    title: str = Field(..., min_length=5, max_length=255)
    summary: str = Field(..., min_length=10)
    description: str = Field(..., min_length=20)
    acceptance_criteria: List[AcceptanceCriteria] = Field(default_factory=list)
    priority: Priority
    priority_reasoning: str
    labels: List[str] = Field(default_factory=list)
    linked_epic_key: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    source_references: List[str] = Field(default_factory=list)
    project_key: str

    @field_validator("labels", mode="before")
    @classmethod
    def normalise_labels(cls, v: List[str]) -> List[str]:
        return [lbl.lower().replace(" ", "-") for lbl in v] if v else []


class ReviewResult(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|CHANGES_REQUIRED)$")
    feedback: str


class ExplainerOutput(BaseModel):
    principles: List[str]
    applied_to_this_ticket: List[str]


class CreatedIssue(BaseModel):
    jira_key: Optional[str] = None
    issue_type: str
    title: str
    url: Optional[str] = None
    error: Optional[str] = None


class DedupeMatch(BaseModel):
    jira_key: str
    title: str
    similarity_score: float
    summary: str
    issue_type: Optional[str] = None
    priority: Optional[str] = None
    url: Optional[str] = None

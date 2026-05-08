from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.domain.document import DocumentStatus, DocumentType


class DocumentChecklistRequest(BaseModel):
    loan_number: str = Field(min_length=1, max_length=50)
    loan_program: str = Field(min_length=1, max_length=50, description="E.g., CONV_30, FHA_30")
    income_type: str = Field(default="W2")


class DocumentStatusUpdateRequest(BaseModel):
    loan_number: str
    doc_type: DocumentType
    status: DocumentStatus
    notes: str | None = Field(default=None, max_length=500)


class DocumentClassificationRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] = {}
    raw_text_snippet: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional text excerpt for AI classification",
    )

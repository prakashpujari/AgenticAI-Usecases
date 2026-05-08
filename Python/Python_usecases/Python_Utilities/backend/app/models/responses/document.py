from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.domain.document import ClassificationResult, DocumentItem, DocumentType


class DocumentChecklistResponse(BaseModel):
    loan_number: str
    loan_program: str
    items: list[DocumentItem]
    completeness_score: float = Field(ge=0.0, le=1.0)
    missing_required: list[DocumentType]
    generated_at: datetime


class DocumentClassificationResponse(BaseModel):
    filename: str
    classification: ClassificationResult
    completeness_contribution: float | None = None

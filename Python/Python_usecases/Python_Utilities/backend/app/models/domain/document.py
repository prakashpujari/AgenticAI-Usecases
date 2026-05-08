from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    W2 = "W2"
    FORM_1099 = "FORM_1099"
    PAYSTUB = "PAYSTUB"
    BANK_STATEMENT = "BANK_STATEMENT"
    TAX_RETURN = "TAX_RETURN"
    SCHEDULE_C = "SCHEDULE_C"
    PROFIT_LOSS = "PROFIT_LOSS"
    PURCHASE_CONTRACT = "PURCHASE_CONTRACT"
    APPRAISAL = "APPRAISAL"
    TITLE_COMMITMENT = "TITLE_COMMITMENT"
    HOMEOWNERS_INSURANCE = "HOMEOWNERS_INSURANCE"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"
    SOCIAL_SECURITY_CARD = "SOCIAL_SECURITY_CARD"
    GIFT_LETTER = "GIFT_LETTER"
    UNKNOWN = "UNKNOWN"


class DocumentStatus(StrEnum):
    RECEIVED = "RECEIVED"
    MISSING = "MISSING"
    PENDING_REVIEW = "PENDING_REVIEW"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class DocumentItem(BaseModel):
    doc_type: DocumentType
    label: str
    description: str
    required: bool
    status: DocumentStatus = DocumentStatus.MISSING
    received_at: datetime | None = None
    notes: str | None = None
    ai_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = {}


class DocumentChecklist(BaseModel):
    loan_number: str
    loan_program: str
    items: list[DocumentItem]
    completeness_score: float = Field(ge=0.0, le=1.0)
    missing_required: list[DocumentType] = []
    generated_at: datetime

    model_config = {"from_attributes": True}


class ClassificationResult(BaseModel):
    predicted_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    alternative_types: list[dict[str, Any]] = []
    provider: str
    latency_ms: float
    raw_metadata: dict[str, Any] = {}

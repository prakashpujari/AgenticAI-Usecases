from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class LoanProgram(StrEnum):
    CONV_30 = "CONV_30"
    CONV_15 = "CONV_15"
    FHA_30 = "FHA_30"
    FHA_15 = "FHA_15"
    VA_30 = "VA_30"
    JUMBO_30 = "JUMBO_30"


class IncomeType(StrEnum):
    W2 = "W2"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    RETIREMENT = "RETIREMENT"
    RENTAL = "RENTAL"
    OTHER = "OTHER"


class LoanPurpose(StrEnum):
    PURCHASE = "PURCHASE"
    REFINANCE = "REFINANCE"
    CASH_OUT_REFI = "CASH_OUT_REFI"


class PropertyType(StrEnum):
    SINGLE_FAMILY = "SINGLE_FAMILY"
    CONDO = "CONDO"
    TOWNHOUSE = "TOWNHOUSE"
    MULTI_FAMILY = "MULTI_FAMILY"


class RiskFlag(BaseModel):
    code: str
    severity: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    description: str
    recommendation: str | None = None


class BorrowerProfile(BaseModel):
    """Core borrower domain entity (internal use, may contain PII)."""

    id: str
    loan_number: str
    first_name: str
    last_name: str
    ssn_last4: str = Field(max_length=4, min_length=4, pattern=r"^\d{4}$")
    date_of_birth: date | None = None
    email: str | None = None
    phone: str | None = None

    # Loan details
    loan_amount: float = Field(gt=0)
    property_value: float = Field(gt=0)
    loan_purpose: LoanPurpose
    property_type: PropertyType

    # Financial
    annual_income: float = Field(ge=0)
    income_type: IncomeType
    monthly_debts: float = Field(ge=0)
    credit_score: int = Field(ge=300, le=850)

    # Computed (cached)
    dti_ratio: float | None = None
    ltv_ratio: float | None = None
    risk_flags: list[RiskFlag] = []

    # Metadata
    loan_program: str | None = None
    loan_officer: str | None = None
    extra: dict[str, Any] = {}

    model_config = {"from_attributes": True}

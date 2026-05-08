from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.domain.borrower import IncomeType, LoanPurpose


class RuleEvaluationRequest(BaseModel):
    loan_number: str | None = None
    credit_score: int = Field(ge=300, le=850)
    dti_ratio: float = Field(ge=0, le=100, description="DTI as a percentage")
    ltv_ratio: float = Field(ge=0, le=200, description="LTV as a percentage")
    loan_program: str = Field(min_length=1, max_length=50)
    income_type: IncomeType
    loan_purpose: LoanPurpose
    loan_amount: float = Field(gt=0)
    property_value: float = Field(gt=0)
    annual_income: float = Field(gt=0)
    additional_attributes: dict[str, Any] = {}


class ScenarioRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    loan_amount: float = Field(gt=0)
    interest_rate: float = Field(gt=0, le=30)
    term_months: int = Field(gt=0, le=480)
    property_value: float = Field(gt=0)
    annual_income: float = Field(gt=0)
    monthly_debts: float = Field(ge=0)


class ScenarioComparisonRequest(BaseModel):
    scenarios: list[ScenarioRequest] = Field(min_length=2, max_length=5)
    idempotency_key: str | None = None

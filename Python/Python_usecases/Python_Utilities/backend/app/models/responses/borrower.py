from __future__ import annotations

from pydantic import BaseModel

from app.models.domain.borrower import IncomeType, LoanPurpose, PropertyType, RiskFlag


class BorrowerSummaryResponse(BaseModel):
    """Redacted borrower view — no full SSN, DOB masked."""

    id: str
    loan_number: str
    first_name: str
    last_name: str
    ssn_last4: str
    loan_amount: float
    property_value: float
    loan_purpose: LoanPurpose
    property_type: PropertyType
    annual_income: float
    income_type: IncomeType
    monthly_debts: float
    credit_score: int
    dti_ratio: float | None
    ltv_ratio: float | None
    risk_flags: list[RiskFlag]
    loan_program: str | None


class DTICalculationResponse(BaseModel):
    front_end_ratio: float  # housing-only / income
    back_end_ratio: float   # (housing + all debts) / income
    monthly_income: float
    total_monthly_obligations: float
    proposed_monthly_payment: float
    passes_threshold: bool
    threshold_used: float
    risk_level: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"


class LTVCalculationResponse(BaseModel):
    ltv_ratio: float          # percent
    loan_amount: float
    property_value: float
    equity_amount: float
    down_payment: float
    pmi_required: bool
    risk_level: str

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.domain.borrower import IncomeType, LoanPurpose, PropertyType


class BorrowerLookupRequest(BaseModel):
    loan_number: str | None = Field(default=None, min_length=1, max_length=50)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    ssn_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    first_name: str | None = Field(default=None, min_length=1, max_length=100)


class DTICalculationRequest(BaseModel):
    annual_income: float = Field(gt=0, description="Gross annual income in USD")
    monthly_debts: float = Field(ge=0, description="Total monthly debt obligations in USD")
    proposed_monthly_payment: float = Field(
        ge=0, description="Proposed new mortgage monthly payment in USD"
    )
    include_housing_ratio: bool = True


class LTVCalculationRequest(BaseModel):
    loan_amount: float = Field(gt=0, description="Loan amount in USD")
    property_value: float = Field(gt=0, description="Appraised property value in USD")
    down_payment: float | None = Field(
        default=None, ge=0, description="Down payment (computed if not supplied)"
    )


class EligibilityCheckRequest(BaseModel):
    credit_score: int = Field(ge=300, le=850)
    dti_ratio: float = Field(ge=0, le=100, description="DTI as a percentage (e.g., 43.5)")
    ltv_ratio: float = Field(ge=0, le=200, description="LTV as a percentage (e.g., 80)")
    loan_program: str = Field(min_length=1, max_length=50, description="E.g., CONV_30, FHA_30")
    income_type: IncomeType
    loan_purpose: LoanPurpose

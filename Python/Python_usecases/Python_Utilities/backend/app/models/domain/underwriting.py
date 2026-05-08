from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RuleResult(BaseModel):
    rule_id: str
    name: str
    description: str
    passed: bool
    severity: str  # "INFO" | "WARNING" | "CRITICAL"
    actual_value: Any
    threshold: Any
    explanation: str
    recommendation: str | None = None


class EvaluationSummary(BaseModel):
    total_rules: int
    passed: int
    failed: int
    critical_failures: int
    overall_pass: bool
    risk_score: float = Field(ge=0.0, le=100.0)


class UnderwritingEvaluation(BaseModel):
    evaluation_id: str
    loan_number: str | None
    rule_results: list[RuleResult]
    summary: EvaluationSummary
    risk_flags: list[dict[str, Any]] = []

    model_config = {"from_attributes": True}


class LoanScenario(BaseModel):
    scenario_id: str
    name: str
    loan_amount: float = Field(gt=0)
    interest_rate: float = Field(gt=0, le=30)  # percent
    term_months: int = Field(gt=0, le=480)
    property_value: float = Field(gt=0)
    annual_income: float = Field(gt=0)
    monthly_debts: float = Field(ge=0)

    # Computed
    monthly_payment: float | None = None
    dti_ratio: float | None = None
    ltv_ratio: float | None = None
    risk_flags: list[dict[str, Any]] = []


class ScenarioComparison(BaseModel):
    comparison_id: str
    scenarios: list[LoanScenario]
    recommended_scenario_id: str | None = None
    notes: str | None = None

from __future__ import annotations

from pydantic import BaseModel

from app.models.domain.underwriting import (
    EvaluationSummary,
    LoanScenario,
    RuleResult,
    ScenarioComparison,
)


class RuleEvaluationResponse(BaseModel):
    evaluation_id: str
    loan_number: str | None
    rule_results: list[RuleResult]
    summary: EvaluationSummary
    risk_flags: list[dict] = []


class ScenarioComparisonResponse(BaseModel):
    comparison_id: str
    scenarios: list[LoanScenario]
    recommended_scenario_id: str | None
    notes: str | None

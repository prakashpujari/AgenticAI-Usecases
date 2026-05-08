from __future__ import annotations

import uuid
from typing import Any

from app.models.domain.underwriting import (
    EvaluationSummary,
    LoanScenario,
    ScenarioComparison,
    UnderwritingEvaluation,
)
from app.models.requests.underwriting import RuleEvaluationRequest, ScenarioComparisonRequest
from app.models.responses.underwriting import RuleEvaluationResponse, ScenarioComparisonResponse
from app.repositories.scenario_repository import ScenarioRepository
from app.services.calculator_service import CalculatorService
from app.services.rule_engine import get_rules_for_program


class UnderwritingService:
    def __init__(
        self,
        scenario_repo: ScenarioRepository,
        calculator: CalculatorService,
    ) -> None:
        self._repo = scenario_repo
        self._calc = calculator

    def evaluate_rules(self, request: RuleEvaluationRequest) -> RuleEvaluationResponse:
        rules = get_rules_for_program(request.loan_program)

        attrs: dict[str, Any] = {
            "credit_score": request.credit_score,
            "dti_ratio": request.dti_ratio,
            "ltv_ratio": request.ltv_ratio,
            "loan_amount": request.loan_amount,
            "property_value": request.property_value,
            "annual_income": request.annual_income,
            "income_type": request.income_type.value,
            "loan_purpose": request.loan_purpose.value,
            **request.additional_attributes,
        }

        results = [rule.evaluate(attrs) for rule in rules]

        failed = [r for r in results if not r.passed]
        critical_failures = sum(1 for r in failed if r.severity == "CRITICAL")
        overall_pass = critical_failures == 0

        # Risk score: 0 (best) → 100 (worst)
        risk_score = min(
            100.0,
            (len(failed) / len(results)) * 60 + critical_failures * 20,
        ) if results else 0.0

        summary = EvaluationSummary(
            total_rules=len(results),
            passed=len(results) - len(failed),
            failed=len(failed),
            critical_failures=critical_failures,
            overall_pass=overall_pass,
            risk_score=round(risk_score, 1),
        )

        risk_flags: list[dict[str, Any]] = [
            {"code": r.rule_id, "severity": r.severity, "description": r.explanation}
            for r in failed
        ]

        return RuleEvaluationResponse(
            evaluation_id=str(uuid.uuid4()),
            loan_number=request.loan_number,
            rule_results=results,
            summary=summary,
            risk_flags=risk_flags,
        )

    async def create_scenario_comparison(
        self, request: ScenarioComparisonRequest
    ) -> ScenarioComparisonResponse:
        scenarios: list[LoanScenario] = []
        for s in request.scenarios:
            scenario_id = str(uuid.uuid4())[:8]
            monthly_payment = CalculatorService.calculate_monthly_payment(
                s.loan_amount, s.interest_rate, s.term_months
            )
            monthly_income = s.annual_income / 12.0
            dti = round(
                ((s.monthly_debts + monthly_payment) / monthly_income) * 100.0, 2
            )
            ltv = round((s.loan_amount / s.property_value) * 100.0, 2)

            risk_flags: list[dict[str, Any]] = []
            if dti > 43:
                risk_flags.append({"code": "HIGH_DTI", "severity": "HIGH", "dti": dti})
            if ltv > 80:
                risk_flags.append({"code": "PMI_REQUIRED", "severity": "MEDIUM", "ltv": ltv})
            if ltv > 97:
                risk_flags.append({"code": "VERY_HIGH_LTV", "severity": "CRITICAL", "ltv": ltv})

            scenarios.append(
                LoanScenario(
                    scenario_id=scenario_id,
                    name=s.name,
                    loan_amount=s.loan_amount,
                    interest_rate=s.interest_rate,
                    term_months=s.term_months,
                    property_value=s.property_value,
                    annual_income=s.annual_income,
                    monthly_debts=s.monthly_debts,
                    monthly_payment=monthly_payment,
                    dti_ratio=dti,
                    ltv_ratio=ltv,
                    risk_flags=risk_flags,
                )
            )

        # Recommend the scenario with lowest risk score (DTI-weighted)
        best = min(
            scenarios,
            key=lambda sc: (sc.dti_ratio or 999) + (sc.ltv_ratio or 999) * 0.1,
        )

        comparison = ScenarioComparison(
            comparison_id=str(uuid.uuid4()),
            scenarios=scenarios,
            recommended_scenario_id=best.scenario_id,
            notes="Recommendation based on lowest combined DTI + LTV risk.",
        )
        await self._repo.save(comparison)

        return ScenarioComparisonResponse(
            comparison_id=comparison.comparison_id,
            scenarios=scenarios,
            recommended_scenario_id=best.scenario_id,
            notes=comparison.notes,
        )

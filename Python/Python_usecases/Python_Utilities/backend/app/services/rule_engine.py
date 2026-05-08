from __future__ import annotations

from typing import Any

from app.models.domain.underwriting import RuleResult


class RuleDefinition:
    """Encapsulates a single underwriting rule."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        description: str,
        severity: str,
        recommendation: str | None = None,
    ) -> None:
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self.severity = severity
        self.recommendation = recommendation

    def evaluate(self, attributes: dict[str, Any]) -> RuleResult:
        raise NotImplementedError


class MinFICORule(RuleDefinition):
    def __init__(self, min_score: int, loan_program: str) -> None:
        super().__init__(
            rule_id=f"FICO_MIN_{loan_program}",
            name=f"Minimum Credit Score ({loan_program})",
            description=f"Credit score must be ≥ {min_score} for {loan_program}",
            severity="CRITICAL",
            recommendation=f"Minimum required FICO is {min_score}. Consider credit improvement strategies.",
        )
        self._min = min_score

    def evaluate(self, attrs: dict[str, Any]) -> RuleResult:
        score = attrs.get("credit_score", 0)
        passed = score >= self._min
        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            description=self.description,
            passed=passed,
            severity=self.severity,
            actual_value=score,
            threshold=self._min,
            explanation=f"Credit score {score} {'meets' if passed else 'does not meet'} the minimum of {self._min}",
            recommendation=None if passed else self.recommendation,
        )


class MaxDTIRule(RuleDefinition):
    def __init__(self, max_dti: float, loan_program: str) -> None:
        super().__init__(
            rule_id=f"DTI_MAX_{loan_program}",
            name=f"Maximum DTI ({loan_program})",
            description=f"Back-end DTI must be ≤ {max_dti}% for {loan_program}",
            severity="CRITICAL",
            recommendation="Reduce monthly debts or increase income to lower DTI",
        )
        self._max = max_dti

    def evaluate(self, attrs: dict[str, Any]) -> RuleResult:
        dti = attrs.get("dti_ratio", 0.0)
        passed = dti <= self._max
        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            description=self.description,
            passed=passed,
            severity=self.severity,
            actual_value=dti,
            threshold=self._max,
            explanation=f"DTI {dti:.1f}% {'is within' if passed else 'exceeds'} the maximum of {self._max}%",
            recommendation=None if passed else self.recommendation,
        )


class MaxLTVRule(RuleDefinition):
    def __init__(self, max_ltv: float, loan_program: str) -> None:
        super().__init__(
            rule_id=f"LTV_MAX_{loan_program}",
            name=f"Maximum LTV ({loan_program})",
            description=f"LTV must be ≤ {max_ltv}% for {loan_program}",
            severity="CRITICAL",
            recommendation="Increase down payment or reduce loan amount to lower LTV",
        )
        self._max = max_ltv

    def evaluate(self, attrs: dict[str, Any]) -> RuleResult:
        ltv = attrs.get("ltv_ratio", 0.0)
        passed = ltv <= self._max
        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            description=self.description,
            passed=passed,
            severity=self.severity,
            actual_value=ltv,
            threshold=self._max,
            explanation=f"LTV {ltv:.1f}% {'is within' if passed else 'exceeds'} the maximum of {self._max}%",
            recommendation=None if passed else self.recommendation,
        )


class MinLoanAmountRule(RuleDefinition):
    def __init__(self, min_amount: float, loan_program: str) -> None:
        super().__init__(
            rule_id=f"LOAN_AMT_MIN_{loan_program}",
            name=f"Minimum Loan Amount ({loan_program})",
            description=f"Loan amount must be ≥ ${min_amount:,.0f} for {loan_program}",
            severity="WARNING",
        )
        self._min = min_amount

    def evaluate(self, attrs: dict[str, Any]) -> RuleResult:
        amount = attrs.get("loan_amount", 0.0)
        passed = amount >= self._min
        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            description=self.description,
            passed=passed,
            severity=self.severity,
            actual_value=amount,
            threshold=self._min,
            explanation=f"Loan amount ${amount:,.0f} {'meets' if passed else 'does not meet'} minimum ${self._min:,.0f}",
        )


# ── Rule registry (config-driven) ─────────────────────────────────────────────

_PROGRAM_RULES: dict[str, list[RuleDefinition]] = {
    "CONV_30": [
        MinFICORule(620, "CONV_30"),
        MaxDTIRule(45.0, "CONV_30"),
        MaxLTVRule(97.0, "CONV_30"),
        MinLoanAmountRule(50_000, "CONV_30"),
    ],
    "FHA_30": [
        MinFICORule(580, "FHA_30"),
        MaxDTIRule(57.0, "FHA_30"),
        MaxLTVRule(96.5, "FHA_30"),
    ],
    "VA_30": [
        MinFICORule(580, "VA_30"),
        MaxDTIRule(41.0, "VA_30"),
        MaxLTVRule(100.0, "VA_30"),
    ],
    "JUMBO_30": [
        MinFICORule(720, "JUMBO_30"),
        MaxDTIRule(43.0, "JUMBO_30"),
        MaxLTVRule(80.0, "JUMBO_30"),
        MinLoanAmountRule(726_201, "JUMBO_30"),
    ],
}

_DEFAULT_RULES: list[RuleDefinition] = [
    MinFICORule(620, "DEFAULT"),
    MaxDTIRule(43.0, "DEFAULT"),
    MaxLTVRule(97.0, "DEFAULT"),
]


def get_rules_for_program(loan_program: str) -> list[RuleDefinition]:
    return _PROGRAM_RULES.get(loan_program.upper(), _DEFAULT_RULES)

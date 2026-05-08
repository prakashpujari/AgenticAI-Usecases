from __future__ import annotations

import pytest

from app.models.domain.borrower import LoanProgram
from app.services.rule_engine import (
    MaxDTIRule,
    MaxLTVRule,
    MinFICORule,
    MinLoanAmountRule,
    get_rules_for_program,
)


# ── MinFICORule ───────────────────────────────────────────────────────────────

class TestMinFICORule:
    def test_passes_at_threshold(self) -> None:
        rule = MinFICORule(620)
        result = rule.evaluate(fico_score=620, dti=30, ltv=80, loan_amount=200_000)
        assert result.passed is True

    def test_fails_below_threshold(self) -> None:
        rule = MinFICORule(620)
        result = rule.evaluate(fico_score=619, dti=30, ltv=80, loan_amount=200_000)
        assert result.passed is False

    def test_severity_is_critical(self) -> None:
        rule = MinFICORule(620)
        result = rule.evaluate(fico_score=500, dti=30, ltv=80, loan_amount=200_000)
        assert result.severity.upper() == "CRITICAL"


# ── MaxDTIRule ────────────────────────────────────────────────────────────────

class TestMaxDTIRule:
    def test_passes_at_threshold(self) -> None:
        rule = MaxDTIRule(45.0)
        result = rule.evaluate(fico_score=700, dti=45.0, ltv=80, loan_amount=200_000)
        assert result.passed is True

    def test_fails_above_threshold(self) -> None:
        rule = MaxDTIRule(45.0)
        result = rule.evaluate(fico_score=700, dti=45.1, ltv=80, loan_amount=200_000)
        assert result.passed is False


# ── MaxLTVRule ────────────────────────────────────────────────────────────────

class TestMaxLTVRule:
    def test_passes_at_threshold(self) -> None:
        rule = MaxLTVRule(97.0)
        result = rule.evaluate(fico_score=700, dti=30, ltv=97.0, loan_amount=200_000)
        assert result.passed is True

    def test_fails_above_threshold(self) -> None:
        rule = MaxLTVRule(97.0)
        result = rule.evaluate(fico_score=700, dti=30, ltv=97.1, loan_amount=200_000)
        assert result.passed is False


# ── MinLoanAmountRule ─────────────────────────────────────────────────────────

class TestMinLoanAmountRule:
    def test_passes_above_minimum(self) -> None:
        rule = MinLoanAmountRule(50_000)
        result = rule.evaluate(fico_score=700, dti=30, ltv=80, loan_amount=100_000)
        assert result.passed is True

    def test_fails_below_minimum(self) -> None:
        rule = MinLoanAmountRule(50_000)
        result = rule.evaluate(fico_score=700, dti=30, ltv=80, loan_amount=49_999)
        assert result.passed is False


# ── get_rules_for_program ─────────────────────────────────────────────────────

class TestGetRulesForProgram:
    def test_conv30_has_rules(self) -> None:
        rules = get_rules_for_program(LoanProgram.CONV_30)
        assert len(rules) > 0

    def test_jumbo30_has_stricter_fico(self) -> None:
        rules = get_rules_for_program(LoanProgram.JUMBO_30)
        fico_rules = [r for r in rules if isinstance(r, MinFICORule)]
        assert len(fico_rules) == 1
        assert fico_rules[0].min_fico >= 720

    def test_va30_allows_100_ltv(self) -> None:
        rules = get_rules_for_program(LoanProgram.VA_30)
        ltv_rules = [r for r in rules if isinstance(r, MaxLTVRule)]
        assert len(ltv_rules) == 1
        assert ltv_rules[0].max_ltv == pytest.approx(100.0)

    def test_unknown_program_returns_empty_or_default(self) -> None:
        # Should not raise
        try:
            rules = get_rules_for_program("UNKNOWN_PROGRAM")  # type: ignore[arg-type]
            assert isinstance(rules, list)
        except (KeyError, ValueError):
            pass  # either behaviour is acceptable

from __future__ import annotations

import pytest
from decimal import Decimal

from app.models.domain.borrower import LoanProgram
from app.models.requests.borrower import DTICalculationRequest, LTVCalculationRequest
from app.services.calculator_service import CalculatorService


@pytest.fixture()
def svc() -> CalculatorService:
    return CalculatorService()


# ── Monthly payment ───────────────────────────────────────────────────────────

class TestCalculateMonthlyPayment:
    def test_standard_30yr(self, svc: CalculatorService) -> None:
        # $200,000 @ 6% / 30 years
        payment = svc.calculate_monthly_payment(200_000, 6.0, 360)
        assert round(payment, 2) == 1199.10

    def test_zero_rate_returns_principal_divided_by_term(self, svc: CalculatorService) -> None:
        payment = svc.calculate_monthly_payment(120_000, 0.0, 120)
        assert round(payment, 2) == 1000.00

    def test_short_term_higher_payment(self, svc: CalculatorService) -> None:
        p30 = svc.calculate_monthly_payment(200_000, 6.0, 360)
        p15 = svc.calculate_monthly_payment(200_000, 6.0, 180)
        assert p15 > p30


# ── DTI ───────────────────────────────────────────────────────────────────────

class TestCalculateDTI:
    def _req(self, **kwargs) -> DTICalculationRequest:
        defaults = dict(
            annual_income=120_000,   # 10_000/mo * 12
            monthly_debts=500,
            proposed_monthly_payment=2_000,
        )
        defaults.update(kwargs)
        return DTICalculationRequest(**defaults)

    def test_back_end_ratio(self, svc: CalculatorService) -> None:
        req = self._req(annual_income=120_000, monthly_debts=500, proposed_monthly_payment=2_000)
        result = svc.calculate_dti(req, LoanProgram.CONV_30)
        # back-end = (500 + 2000) / (120000/12) = 25%
        assert result.back_end_ratio == pytest.approx(25.0, abs=0.01)

    def test_front_end_ratio(self, svc: CalculatorService) -> None:
        req = self._req(annual_income=120_000, proposed_monthly_payment=2_500)
        result = svc.calculate_dti(req, LoanProgram.CONV_30)
        # front-end = 2500 / (120000/12) = 25%
        assert result.front_end_ratio == pytest.approx(25.0, abs=0.01)

    def test_passes_conventional_threshold(self, svc: CalculatorService) -> None:
        # back-end 30% — well under 45%
        req = self._req(annual_income=120_000, monthly_debts=0, proposed_monthly_payment=3_000)
        result = svc.calculate_dti(req, LoanProgram.CONV_30)
        assert result.passes_threshold is True

    def test_fails_conventional_threshold(self, svc: CalculatorService) -> None:
        # back-end 50% — over 45%
        req = self._req(annual_income=120_000, monthly_debts=2_000, proposed_monthly_payment=3_000)
        result = svc.calculate_dti(req, LoanProgram.CONV_30)
        assert result.passes_threshold is False

    def test_risk_level_low(self, svc: CalculatorService) -> None:
        req = self._req(annual_income=120_000, monthly_debts=0, proposed_monthly_payment=2_000)
        result = svc.calculate_dti(req, LoanProgram.CONV_30)
        assert result.risk_level == "LOW"

    def test_fha_higher_threshold(self, svc: CalculatorService) -> None:
        # FHA allows 57%; 50% back-end should pass
        req = self._req(annual_income=120_000, monthly_debts=2_000, proposed_monthly_payment=3_000)
        result = svc.calculate_dti(req, LoanProgram.FHA_30)
        assert result.passes_threshold is True


# ── LTV ───────────────────────────────────────────────────────────────────────

class TestCalculateLTV:
    def _req(self, **kwargs) -> LTVCalculationRequest:
        defaults = dict(loan_amount=160_000, property_value=200_000)
        defaults.update(kwargs)
        return LTVCalculationRequest(**defaults)

    def test_basic_ltv(self, svc: CalculatorService) -> None:
        result = svc.calculate_ltv(self._req())
        assert result.ltv_ratio == pytest.approx(80.0, abs=0.01)

    def test_pmi_required_above_80(self, svc: CalculatorService) -> None:
        result = svc.calculate_ltv(self._req(loan_amount=170_000, property_value=200_000))
        assert result.pmi_required is True

    def test_pmi_not_required_at_80(self, svc: CalculatorService) -> None:
        result = svc.calculate_ltv(self._req(loan_amount=160_000, property_value=200_000))
        assert result.pmi_required is False

    def test_risk_level_critical_above_95(self, svc: CalculatorService) -> None:
        result = svc.calculate_ltv(self._req(loan_amount=196_000, property_value=200_000))
        assert result.risk_level == "CRITICAL"

    def test_down_payment_calculated(self, svc: CalculatorService) -> None:
        result = svc.calculate_ltv(self._req(loan_amount=160_000, property_value=200_000))
        assert result.down_payment == pytest.approx(40_000.0, abs=0.01)

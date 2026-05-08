from __future__ import annotations

from dataclasses import dataclass

from app.models.domain.borrower import RiskFlag
from app.models.requests.borrower import DTICalculationRequest, LTVCalculationRequest
from app.models.responses.borrower import DTICalculationResponse, LTVCalculationResponse

# Industry-standard DTI thresholds
_DTI_THRESHOLDS: dict[str, float] = {
    "CONV_30": 45.0,
    "CONV_15": 43.0,
    "FHA_30": 57.0,
    "FHA_15": 57.0,
    "VA_30": 41.0,
    "JUMBO_30": 43.0,
    "DEFAULT": 43.0,
}

_LTV_PMI_THRESHOLD = 80.0  # percent


@dataclass(frozen=True)
class _RiskLevel:
    label: str

    @staticmethod
    def from_dti(dti: float) -> str:
        if dti < 36:
            return "LOW"
        if dti < 43:
            return "MEDIUM"
        if dti < 50:
            return "HIGH"
        return "CRITICAL"

    @staticmethod
    def from_ltv(ltv: float) -> str:
        if ltv <= 80:
            return "LOW"
        if ltv <= 90:
            return "MEDIUM"
        if ltv <= 95:
            return "HIGH"
        return "CRITICAL"


class CalculatorService:
    """
    Pure, stateless calculator service.
    No I/O — easy to unit-test and reuse from any context.
    """

    def calculate_dti(
        self,
        request: DTICalculationRequest,
        loan_program: str = "DEFAULT",
    ) -> DTICalculationResponse:
        monthly_income = request.annual_income / 12.0
        if monthly_income <= 0:
            raise ValueError("Annual income must be greater than zero")

        total_obligations = request.monthly_debts + request.proposed_monthly_payment
        back_end_ratio = (total_obligations / monthly_income) * 100.0
        front_end_ratio = (request.proposed_monthly_payment / monthly_income) * 100.0

        threshold = _DTI_THRESHOLDS.get(loan_program.upper(), _DTI_THRESHOLDS["DEFAULT"])

        return DTICalculationResponse(
            front_end_ratio=round(front_end_ratio, 2),
            back_end_ratio=round(back_end_ratio, 2),
            monthly_income=round(monthly_income, 2),
            total_monthly_obligations=round(total_obligations, 2),
            proposed_monthly_payment=round(request.proposed_monthly_payment, 2),
            passes_threshold=back_end_ratio <= threshold,
            threshold_used=threshold,
            risk_level=_RiskLevel.from_dti(back_end_ratio),
        )

    def calculate_ltv(self, request: LTVCalculationRequest) -> LTVCalculationResponse:
        loan_amount = request.loan_amount
        property_value = request.property_value

        ltv = (loan_amount / property_value) * 100.0
        equity = property_value - loan_amount
        down_payment = (
            request.down_payment
            if request.down_payment is not None
            else property_value - loan_amount
        )

        return LTVCalculationResponse(
            ltv_ratio=round(ltv, 2),
            loan_amount=loan_amount,
            property_value=property_value,
            equity_amount=round(equity, 2),
            down_payment=round(down_payment, 2),
            pmi_required=ltv > _LTV_PMI_THRESHOLD,
            risk_level=_RiskLevel.from_ltv(ltv),
        )

    @staticmethod
    def calculate_monthly_payment(
        principal: float,
        annual_rate_pct: float,
        term_months: int,
    ) -> float:
        """Standard amortising mortgage payment (Pmt formula)."""
        if annual_rate_pct == 0:
            return round(principal / term_months, 2)
        r = (annual_rate_pct / 100.0) / 12.0
        payment = principal * (r * (1 + r) ** term_months) / ((1 + r) ** term_months - 1)
        return round(payment, 2)

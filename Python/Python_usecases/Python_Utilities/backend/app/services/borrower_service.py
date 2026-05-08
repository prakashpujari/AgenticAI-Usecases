from __future__ import annotations

from app.core.exceptions import NotFoundError, ValidationError
from app.models.domain.borrower import BorrowerProfile, RiskFlag
from app.models.requests.borrower import BorrowerLookupRequest
from app.models.responses.borrower import BorrowerSummaryResponse
from app.repositories.borrower_repository import BorrowerRepository
from app.services.calculator_service import CalculatorService
from app.models.requests.borrower import DTICalculationRequest, LTVCalculationRequest


class BorrowerService:
    def __init__(
        self,
        borrower_repo: BorrowerRepository,
        calculator: CalculatorService,
    ) -> None:
        self._repo = borrower_repo
        self._calc = calculator

    async def lookup(
        self, request: BorrowerLookupRequest
    ) -> list[BorrowerSummaryResponse]:
        if not any([request.loan_number, request.last_name, request.ssn_last4, request.first_name]):
            raise ValidationError("At least one search filter (loan_number, first_name, last_name, ssn_last4) is required.")
        profiles = await self._repo.search(
            loan_number=request.loan_number,
            last_name=request.last_name,
            ssn_last4=request.ssn_last4,
            first_name=request.first_name,
        )
        return [self._to_summary(p) for p in profiles]

    async def get_by_loan_number(self, loan_number: str) -> BorrowerSummaryResponse:
        profile = await self._repo.get_by_loan_number(loan_number)
        if not profile:
            raise NotFoundError(f"Loan {loan_number!r} not found")
        return self._to_summary(profile)

    def _to_summary(self, profile: BorrowerProfile) -> BorrowerSummaryResponse:
        # Compute fresh DTI / LTV when not already cached
        monthly_payment_estimate = 0.0
        if profile.loan_amount and profile.annual_income:
            from app.services.calculator_service import CalculatorService
            monthly_payment_estimate = CalculatorService.calculate_monthly_payment(
                profile.loan_amount, 7.0, 360
            )

        dti_result = self._calc.calculate_dti(
            DTICalculationRequest(
                annual_income=profile.annual_income,
                monthly_debts=profile.monthly_debts,
                proposed_monthly_payment=monthly_payment_estimate,
            ),
            loan_program=profile.loan_program or "DEFAULT",
        )
        ltv_result = self._calc.calculate_ltv(
            LTVCalculationRequest(
                loan_amount=profile.loan_amount,
                property_value=profile.property_value,
            )
        )

        risk_flags = list(profile.risk_flags)
        if not dti_result.passes_threshold:
            risk_flags.append(
                RiskFlag(
                    code="HIGH_DTI",
                    severity="HIGH",
                    description=f"DTI {dti_result.back_end_ratio:.1f}% exceeds threshold {dti_result.threshold_used}%",
                    recommendation="Review income documentation and reduce monthly obligations",
                )
            )
        if ltv_result.pmi_required:
            risk_flags.append(
                RiskFlag(
                    code="PMI_REQUIRED",
                    severity="MEDIUM",
                    description=f"LTV {ltv_result.ltv_ratio:.1f}% > 80%; PMI will apply",
                    recommendation="Consider a larger down payment to avoid PMI",
                )
            )

        return BorrowerSummaryResponse(
            id=profile.id,
            loan_number=profile.loan_number,
            first_name=profile.first_name,
            last_name=profile.last_name,
            ssn_last4=profile.ssn_last4,
            loan_amount=profile.loan_amount,
            property_value=profile.property_value,
            loan_purpose=profile.loan_purpose,
            property_type=profile.property_type,
            annual_income=profile.annual_income,
            income_type=profile.income_type,
            monthly_debts=profile.monthly_debts,
            credit_score=profile.credit_score,
            dti_ratio=dti_result.back_end_ratio,
            ltv_ratio=ltv_result.ltv_ratio,
            risk_flags=risk_flags,
            loan_program=profile.loan_program,
        )

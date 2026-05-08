from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, require_roles
from app.models.domain.user import Role, UserInDB
from app.models.requests.borrower import (
    DTICalculationRequest,
    EligibilityCheckRequest,
    LTVCalculationRequest,
)
from app.models.responses.borrower import DTICalculationResponse, LTVCalculationResponse
from app.services.calculator_service import CalculatorService
from app.services.rule_engine import get_rules_for_program
from app.models.domain.underwriting import EvaluationSummary

router = APIRouter(prefix="/utilities", tags=["Mortgage Utilities"])

_ALLOWED_ROLES = (Role.UNDERWRITER, Role.OPS, Role.ADMIN)


def _calculator() -> CalculatorService:
    return CalculatorService()


@router.post(
    "/dti",
    response_model=DTICalculationResponse,
    summary="Calculate Debt-to-Income ratio",
    description=(
        "Compute front-end and back-end DTI ratios from income and debt figures. "
        "Pass an optional `loan_program` query parameter for program-specific thresholds."
    ),
)
async def calculate_dti(
    request: DTICalculationRequest,
    _: Annotated[UserInDB, Depends(require_roles(*_ALLOWED_ROLES))],
    calc: Annotated[CalculatorService, Depends(_calculator)],
    loan_program: str = Query(default="DEFAULT", description="Loan program code, e.g. CONV_30"),
) -> DTICalculationResponse:
    return calc.calculate_dti(request, loan_program=loan_program)


@router.post(
    "/ltv",
    response_model=LTVCalculationResponse,
    summary="Calculate Loan-to-Value ratio",
    description=(
        "Compute LTV, equity, and PMI requirement from loan amount and property value."
    ),
)
async def calculate_ltv(
    request: LTVCalculationRequest,
    _: Annotated[UserInDB, Depends(require_roles(*_ALLOWED_ROLES))],
    calc: Annotated[CalculatorService, Depends(_calculator)],
) -> LTVCalculationResponse:
    return calc.calculate_ltv(request)


@router.post(
    "/eligibility",
    summary="Quick eligibility check",
    description="Run the rule engine for a given program and return pass/fail summary.",
)
async def check_eligibility(
    request: EligibilityCheckRequest,
    _: Annotated[UserInDB, Depends(require_roles(*_ALLOWED_ROLES))],
) -> dict:
    rules = get_rules_for_program(request.loan_program)
    attrs = {
        "credit_score": request.credit_score,
        "dti_ratio": request.dti_ratio,
        "ltv_ratio": request.ltv_ratio,
        "loan_amount": 100_000,  # dummy — not relevant for eligibility rules
        "property_value": 100_000,
        "annual_income": 100_000,
        "income_type": request.income_type.value,
        "loan_purpose": request.loan_purpose.value,
    }
    results = [rule.evaluate(attrs) for rule in rules]
    failed = [r for r in results if not r.passed]
    return {
        "eligible": len([r for r in failed if r.severity == "CRITICAL"]) == 0,
        "loan_program": request.loan_program,
        "rules_evaluated": len(results),
        "failures": [{"rule": r.rule_id, "reason": r.explanation} for r in failed],
    }

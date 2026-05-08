from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, require_roles
from app.models.domain.user import Role, UserInDB
from app.models.requests.borrower import BorrowerLookupRequest
from app.models.responses.borrower import BorrowerSummaryResponse
from app.repositories.borrower_repository import BorrowerRepository, get_borrower_repository
from app.services.borrower_service import BorrowerService
from app.services.calculator_service import CalculatorService

router = APIRouter(prefix="/borrowers", tags=["Borrower Utilities"])

_ALLOWED_ROLES = (Role.UNDERWRITER, Role.OPS, Role.ADMIN)


def _borrower_service(
    repo: Annotated[BorrowerRepository, Depends(get_borrower_repository)],
) -> BorrowerService:
    return BorrowerService(repo, CalculatorService())


@router.get(
    "/search",
    response_model=list[BorrowerSummaryResponse],
    summary="Search borrower profiles",
    description=(
        "Lookup borrowers by loan number, name, or SSN last-4. "
        "At least one filter is required. Returns redacted profiles (no full SSN)."
    ),
)
async def search_borrowers(
    loan_number: str | None = Query(default=None, description="Exact loan number"),
    last_name: str | None = Query(default=None, description="Borrower last name (exact match)"),
    ssn_last4: str | None = Query(default=None, description="Last 4 digits of SSN", pattern=r"^\d{4}$"),
    first_name: str | None = Query(default=None, description="Borrower first name (exact match)"),
    _current_user: Annotated[UserInDB, Depends(require_roles(*_ALLOWED_ROLES))] = None,
    service: Annotated[BorrowerService, Depends(_borrower_service)] = None,
) -> list[BorrowerSummaryResponse]:
    request = BorrowerLookupRequest(
        loan_number=loan_number or None,
        last_name=last_name or None,
        ssn_last4=ssn_last4 or None,
        first_name=first_name or None,
    )
    return await service.lookup(request)


@router.get(
    "/{loan_number}",
    response_model=BorrowerSummaryResponse,
    summary="Get borrower by loan number",
)
async def get_borrower(
    loan_number: str,
    _current_user: Annotated[UserInDB, Depends(require_roles(*_ALLOWED_ROLES))] = None,
    service: Annotated[BorrowerService, Depends(_borrower_service)] = None,
) -> BorrowerSummaryResponse:
    return await service.get_by_loan_number(loan_number)

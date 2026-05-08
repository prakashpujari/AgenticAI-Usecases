from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.dependencies import get_current_user, require_roles
from app.models.domain.user import Role, UserInDB
from app.models.requests.underwriting import RuleEvaluationRequest, ScenarioComparisonRequest
from app.models.responses.underwriting import RuleEvaluationResponse, ScenarioComparisonResponse
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.scenario_repository import ScenarioRepository, get_scenario_repository
from app.services.calculator_service import CalculatorService
from app.services.underwriting_service import UnderwritingService

router = APIRouter(prefix="/underwriting", tags=["Underwriting Utilities"])

_ALLOWED_ROLES = (Role.UNDERWRITER, Role.ADMIN)


def _uw_service(
    scenario_repo: Annotated[ScenarioRepository, Depends(get_scenario_repository)],
) -> UnderwritingService:
    return UnderwritingService(scenario_repo, CalculatorService())


_idempotency_repo = IdempotencyRepository()  # In-memory; swap for Redis-backed in prod


@router.post(
    "/rules/evaluate",
    response_model=RuleEvaluationResponse,
    summary="Evaluate underwriting rules",
    description=(
        "Run the config-driven rule engine against borrower/loan attributes. "
        "Returns per-rule pass/fail with explanations and an overall risk score."
    ),
)
async def evaluate_rules(
    request: RuleEvaluationRequest,
    _: Annotated[UserInDB, Depends(require_roles(*_ALLOWED_ROLES))],
    service: Annotated[UnderwritingService, Depends(_uw_service)],
) -> RuleEvaluationResponse:
    return service.evaluate_rules(request)


@router.post(
    "/scenarios/compare",
    response_model=ScenarioComparisonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create scenario comparison",
    description=(
        "Compare 2–5 loan scenarios (amount, rate, term). "
        "Supports idempotency via the `Idempotency-Key` header."
    ),
)
async def compare_scenarios(
    request: ScenarioComparisonRequest,
    _: Annotated[UserInDB, Depends(require_roles(*_ALLOWED_ROLES))],
    service: Annotated[UnderwritingService, Depends(_uw_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ScenarioComparisonResponse:
    if idempotency_key:
        cached = await _idempotency_repo.get(idempotency_key)
        if cached:
            return ScenarioComparisonResponse(**cached["body"])

    result = await service.create_scenario_comparison(request)

    if idempotency_key:
        await _idempotency_repo.set(
            idempotency_key,
            result.model_dump(),
            status_code=status.HTTP_201_CREATED,
        )

    return result

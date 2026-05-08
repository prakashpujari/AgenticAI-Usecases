from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, require_roles
from app.infrastructure.ai.mock_provider import create_ai_provider
from app.models.domain.user import Role, UserInDB
from app.models.requests.document import (
    DocumentChecklistRequest,
    DocumentClassificationRequest,
)
from app.models.responses.document import (
    DocumentChecklistResponse,
    DocumentClassificationResponse,
)
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Document Utilities"])

_ALLOWED_ROLES = (Role.UNDERWRITER, Role.OPS, Role.ADMIN)


def _doc_service() -> DocumentService:
    from app.core.config import get_settings
    settings = get_settings()
    return DocumentService(create_ai_provider(settings.ai_provider))


@router.post(
    "/checklist",
    response_model=DocumentChecklistResponse,
    summary="Generate document checklist",
    description=(
        "Generate the required document checklist for a loan based on program and income type. "
        "Returns all required documents with current status (initially MISSING)."
    ),
)
async def generate_checklist(
    request: DocumentChecklistRequest,
    _: Annotated[UserInDB, Depends(require_roles(*_ALLOWED_ROLES))],
    service: Annotated[DocumentService, Depends(_doc_service)],
) -> DocumentChecklistResponse:
    return service.generate_checklist(request)


@router.post(
    "/classify",
    response_model=DocumentClassificationResponse,
    summary="Classify a document",
    description=(
        "Use AI/ML to predict the document type from filename, content-type, "
        "or a text snippet. Backed by a configurable AI provider (mock by default)."
    ),
)
async def classify_document(
    request: DocumentClassificationRequest,
    _: Annotated[UserInDB, Depends(require_roles(*_ALLOWED_ROLES))],
    service: Annotated[DocumentService, Depends(_doc_service)],
) -> DocumentClassificationResponse:
    return await service.classify_document(request)

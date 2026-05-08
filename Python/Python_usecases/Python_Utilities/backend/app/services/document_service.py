from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.infrastructure.ai.base import AIProvider
from app.models.domain.document import (
    ClassificationResult,
    DocumentChecklist,
    DocumentItem,
    DocumentStatus,
    DocumentType,
)
from app.models.requests.document import (
    DocumentChecklistRequest,
    DocumentClassificationRequest,
    DocumentStatusUpdateRequest,
)
from app.models.responses.document import (
    DocumentChecklistResponse,
    DocumentClassificationResponse,
)
from app.services.document_config import (
    _DEFAULT_REQUIREMENTS,
    _DOC_LABELS,
    _PROGRAM_REQUIREMENTS,
)


class DocumentService:
    def __init__(self, ai_provider: AIProvider) -> None:
        self._ai = ai_provider

    def generate_checklist(
        self, request: DocumentChecklistRequest
    ) -> DocumentChecklistResponse:
        program_docs = _PROGRAM_REQUIREMENTS.get(request.loan_program.upper(), {})
        required_keys: list[str] = (
            program_docs.get(request.income_type.upper())
            or program_docs.get("DEFAULT")
            or _DEFAULT_REQUIREMENTS
        )

        items: list[DocumentItem] = []
        for key in required_keys:
            meta = _DOC_LABELS.get(key, {"label": key, "description": ""})
            try:
                doc_type = DocumentType(key)
            except ValueError:
                doc_type = DocumentType.UNKNOWN
            items.append(
                DocumentItem(
                    doc_type=doc_type,
                    label=meta["label"],
                    description=meta["description"],
                    required=True,
                    status=DocumentStatus.MISSING,
                )
            )

        missing_required = [i.doc_type for i in items if i.required and i.status == DocumentStatus.MISSING]
        completeness = 1.0 - (len(missing_required) / len(items)) if items else 1.0

        return DocumentChecklistResponse(
            loan_number=request.loan_number,
            loan_program=request.loan_program,
            items=items,
            completeness_score=round(completeness, 4),
            missing_required=missing_required,
            generated_at=datetime.now(UTC),
        )

    def update_document_status(
        self,
        checklist: DocumentChecklistResponse,
        update: DocumentStatusUpdateRequest,
    ) -> DocumentChecklistResponse:
        updated_items = []
        for item in checklist.items:
            if item.doc_type == update.doc_type:
                item = item.model_copy(
                    update={
                        "status": update.status,
                        "notes": update.notes,
                        "received_at": datetime.now(UTC)
                        if update.status == DocumentStatus.RECEIVED
                        else item.received_at,
                    }
                )
            updated_items.append(item)

        missing_required = [
            i.doc_type
            for i in updated_items
            if i.required and i.status == DocumentStatus.MISSING
        ]
        completeness = 1.0 - (len(missing_required) / len(updated_items)) if updated_items else 1.0

        return DocumentChecklistResponse(
            loan_number=checklist.loan_number,
            loan_program=checklist.loan_program,
            items=updated_items,
            completeness_score=round(completeness, 4),
            missing_required=missing_required,
            generated_at=checklist.generated_at,
        )

    async def classify_document(
        self, request: DocumentClassificationRequest
    ) -> DocumentClassificationResponse:
        t0 = time.perf_counter()
        result = await self._ai.classify_document(
            filename=request.filename,
            content_type=request.content_type,
            text_snippet=request.raw_text_snippet,
            metadata=request.metadata,
        )
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        classification = ClassificationResult(
            predicted_type=result.predicted_type,
            confidence=result.confidence,
            alternative_types=result.alternative_types,
            provider=result.provider,
            latency_ms=latency_ms,
        )

        return DocumentClassificationResponse(
            filename=request.filename,
            classification=classification,
        )

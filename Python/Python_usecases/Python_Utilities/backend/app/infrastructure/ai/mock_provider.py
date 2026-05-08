from __future__ import annotations

import asyncio
import re
from typing import Any

from app.infrastructure.ai.base import (
    AIProvider,
    ClassificationOutput,
    EntityExtractionOutput,
    TextGenerationOutput,
)
from app.models.domain.document import DocumentType

# Heuristic keyword → document-type mapping (mock AI)
_FILENAME_PATTERNS: list[tuple[re.Pattern[str], DocumentType, float]] = [
    (re.compile(r"w[-_]?2", re.I), DocumentType.W2, 0.96),
    (re.compile(r"1099", re.I), DocumentType.FORM_1099, 0.94),
    (re.compile(r"pay.?stub|payslip", re.I), DocumentType.PAYSTUB, 0.93),
    (re.compile(r"bank.?stmt|statement", re.I), DocumentType.BANK_STATEMENT, 0.88),
    (re.compile(r"tax.?return|1040", re.I), DocumentType.TAX_RETURN, 0.91),
    (re.compile(r"schedule.?c", re.I), DocumentType.SCHEDULE_C, 0.90),
    (re.compile(r"p.?&.?l|profit.?loss", re.I), DocumentType.PROFIT_LOSS, 0.87),
    (re.compile(r"purchase|contract", re.I), DocumentType.PURCHASE_CONTRACT, 0.85),
    (re.compile(r"appraisal", re.I), DocumentType.APPRAISAL, 0.92),
    (re.compile(r"title", re.I), DocumentType.TITLE_COMMITMENT, 0.83),
    (re.compile(r"insurance|hazard|homeowner", re.I), DocumentType.HOMEOWNERS_INSURANCE, 0.85),
    (re.compile(r"dl|license|passport|id.?card", re.I), DocumentType.DRIVERS_LICENSE, 0.80),
    (re.compile(r"ssn|social.?security", re.I), DocumentType.SOCIAL_SECURITY_CARD, 0.82),
    (re.compile(r"gift", re.I), DocumentType.GIFT_LETTER, 0.88),
]


class MockAIProvider(AIProvider):
    """
    Deterministic mock provider — no external calls.
    Simulates plausible responses for development, testing, and demos.
    """

    provider_name = "mock"

    async def classify_document(
        self,
        *,
        filename: str,
        content_type: str | None,
        text_snippet: str | None,
        metadata: dict[str, Any],
    ) -> ClassificationOutput:
        # Simulate a small async latency
        await asyncio.sleep(0.05)

        combined = (filename or "") + " " + (text_snippet or "")
        for pattern, doc_type, confidence in _FILENAME_PATTERNS:
            if pattern.search(combined):
                alternatives = [
                    {"type": DocumentType.UNKNOWN.value, "confidence": 1.0 - confidence}
                ]
                return ClassificationOutput(
                    predicted_type=doc_type,
                    confidence=confidence,
                    alternative_types=alternatives,
                    provider=self.provider_name,
                )

        return ClassificationOutput(
            predicted_type=DocumentType.UNKNOWN,
            confidence=0.40,
            alternative_types=[],
            provider=self.provider_name,
        )

    async def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> TextGenerationOutput:
        await asyncio.sleep(0.05)
        return TextGenerationOutput(
            text=(
                f"[MockAI] Generated response for prompt: {prompt[:80]}... "
                "(Replace with real provider implementation)"
            ),
            model="mock-gpt-3.5",
            provider=self.provider_name,
            tokens_used=42,
        )

    async def extract_entities(
        self,
        *,
        text: str,
        entity_types: list[str],
    ) -> EntityExtractionOutput:
        await asyncio.sleep(0.03)
        mock_entities = {et: f"[MOCK_{et.upper()}]" for et in entity_types}
        return EntityExtractionOutput(
            entities=mock_entities,
            provider=self.provider_name,
            confidence=0.75,
        )


def create_ai_provider(provider_name: str = "mock") -> AIProvider:
    """Factory.  Extend to instantiate real providers based on config."""
    if provider_name == "mock":
        return MockAIProvider()
    # Future: elif provider_name == "openai": return OpenAIProvider(...)
    raise ValueError(f"Unknown AI provider: {provider_name!r}")

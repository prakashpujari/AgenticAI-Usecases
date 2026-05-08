from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClassificationOutput:
    predicted_type: Any  # DocumentType
    confidence: float
    alternative_types: list[dict[str, Any]] = field(default_factory=list)
    provider: str = "unknown"
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextGenerationOutput:
    text: str
    model: str
    provider: str
    tokens_used: int | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityExtractionOutput:
    entities: dict[str, Any]
    provider: str
    confidence: float = 1.0


class AIProvider(ABC):
    """
    Hexagonal port for AI/LLM integration.
    Swap implementations (mock, OpenAI, Bedrock, Azure OpenAI) at the DI layer.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    async def classify_document(
        self,
        *,
        filename: str,
        content_type: str | None,
        text_snippet: str | None,
        metadata: dict[str, Any],
    ) -> ClassificationOutput: ...

    @abstractmethod
    async def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> TextGenerationOutput: ...

    @abstractmethod
    async def extract_entities(
        self,
        *,
        text: str,
        entity_types: list[str],
    ) -> EntityExtractionOutput: ...

"""Base agent helpers used by every LangGraph node."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

try:
    from langsmith import traceable
except ImportError:
    def traceable(**_kw):  # type: ignore[misc]
        def _wrap(fn):
            return fn
        return _wrap

from app.models.schemas import AgentReport
from app.services.groq_client import GroqClient

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    name: str = "base"
    role: str = "You are a helpful AI agent."

    def __init__(self, llm: GroqClient | None = None) -> None:
        self.llm = llm or GroqClient()

    @abstractmethod
    def run(self, state: dict[str, Any]) -> AgentReport:
        """Inspect the shared graph state and produce an AgentReport."""

    def _ask_json(self, user_prompt: str) -> dict[str, Any]:
        return self.llm.complete_json(self.role, user_prompt)

    def _ask_text(self, user_prompt: str) -> str:
        return self.llm.complete(self.role, user_prompt)

    def _coerce_score(self, raw: dict[str, Any], default: int = 90) -> int:
        try:
            score = int(raw.get("score", default))
        except (TypeError, ValueError):
            score = default
        return max(0, min(100, score))

    def _traced_ask_json(self, user_prompt: str) -> dict[str, Any]:
        @traceable(name=f"{self.name}/llm_call", run_type="llm", tags=[self.name])
        def _call(prompt: str) -> dict[str, Any]:
            return self.llm.complete_json(self.role, prompt)
        return _call(user_prompt)

    def _traced_ask_text(self, user_prompt: str) -> str:
        @traceable(name=f"{self.name}/llm_call", run_type="llm", tags=[self.name])
        def _call(prompt: str) -> str:
            return self.llm.complete(self.role, prompt)
        return _call(user_prompt)

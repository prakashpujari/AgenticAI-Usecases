from __future__ import annotations

import uuid
from datetime import datetime

from app.models.domain.underwriting import LoanScenario, ScenarioComparison
from app.repositories.base import AbstractRepository


class ScenarioRepository(AbstractRepository[ScenarioComparison, str]):
    """In-memory scenario comparison store."""

    def __init__(self) -> None:
        self._store: dict[str, ScenarioComparison] = {}

    async def get_by_id(self, entity_id: str) -> ScenarioComparison | None:
        return self._store.get(entity_id)

    async def save(self, entity: ScenarioComparison) -> ScenarioComparison:
        self._store[entity.comparison_id] = entity
        return entity

    async def delete(self, entity_id: str) -> bool:
        return self._store.pop(entity_id, None) is not None


# ── Dependency ────────────────────────────────────────────────────────────────

_scenario_repo: ScenarioRepository | None = None


def get_scenario_repository() -> ScenarioRepository:
    global _scenario_repo
    if _scenario_repo is None:
        _scenario_repo = ScenarioRepository()
    return _scenario_repo

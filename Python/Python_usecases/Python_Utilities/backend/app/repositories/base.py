from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")
ID = TypeVar("ID")


class AbstractRepository(ABC, Generic[T, ID]):
    """Thin repository abstraction; swap for SQLAlchemy without touching callers."""

    @abstractmethod
    async def get_by_id(self, entity_id: ID) -> T | None: ...

    @abstractmethod
    async def save(self, entity: T) -> T: ...

    @abstractmethod
    async def delete(self, entity_id: ID) -> bool: ...

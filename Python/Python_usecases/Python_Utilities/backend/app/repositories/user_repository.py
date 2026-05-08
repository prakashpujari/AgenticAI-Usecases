from __future__ import annotations

import uuid
from datetime import date

from app.core.security import hash_password
from app.models.domain.user import Role, UserInDB
from app.repositories.base import AbstractRepository


class UserRepository(AbstractRepository[UserInDB, str]):
    """In-memory user store — replace with SQLAlchemy ORM repo for production."""

    def __init__(self) -> None:
        self._store: dict[str, UserInDB] = {}
        self._username_index: dict[str, str] = {}  # username -> id
        self._email_index: dict[str, str] = {}  # email -> id
        self._seed_demo_users()

    def _seed_demo_users(self) -> None:
        users: list[dict] = [
            {
                "id": "usr_001",
                "username": "underwriter1",
                "email": "uw1@mortgage.internal",
                "full_name": "Alice Underwriter",
                "role": Role.UNDERWRITER,
                "password": "Underwriter@123",
            },
            {
                "id": "usr_002",
                "username": "ops_user1",
                "email": "ops1@mortgage.internal",
                "full_name": "Bob Operations",
                "role": Role.OPS,
                "password": "OpsUser@123",
            },
            {
                "id": "usr_003",
                "username": "admin",
                "email": "admin@mortgage.internal",
                "full_name": "Carol Admin",
                "role": Role.ADMIN,
                "password": "Admin@123456",
            },
        ]
        for u in users:
            user = UserInDB(
                id=u["id"],
                username=u["username"],
                email=u["email"],
                full_name=u["full_name"],
                role=u["role"],
                hashed_password=hash_password(u["password"]),
            )
            self._store[user.id] = user
            self._username_index[user.username] = user.id
            self._email_index[user.email] = user.id

    async def get_by_id(self, entity_id: str) -> UserInDB | None:
        return self._store.get(entity_id)

    async def get_by_username(self, username: str) -> UserInDB | None:
        uid = self._username_index.get(username)
        return self._store.get(uid) if uid else None

    async def get_by_email(self, email: str) -> UserInDB | None:
        uid = self._email_index.get(email)
        return self._store.get(uid) if uid else None

    async def save(self, entity: UserInDB) -> UserInDB:
        self._store[entity.id] = entity
        self._username_index[entity.username] = entity.id
        self._email_index[entity.email] = entity.id
        return entity

    async def delete(self, entity_id: str) -> bool:
        user = self._store.pop(entity_id, None)
        if user:
            self._username_index.pop(user.username, None)
        return user is not None


# ── Dependency injection ──────────────────────────────────────────────────────

_user_repo: UserRepository | None = None


def get_user_repository() -> UserRepository:
    global _user_repo
    if _user_repo is None:
        _user_repo = UserRepository()
    return _user_repo

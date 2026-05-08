from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.main import create_app
from app.core.dependencies import get_current_user
from app.models.domain.user import Role, UserInDB


# ── Fake users ────────────────────────────────────────────────────────────────

def make_user(role: Role = Role.UNDERWRITER) -> UserInDB:
    return UserInDB(
        id="test-user-1",
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        role=role,
        is_active=True,
        hashed_password="$2b$12$fakehash",
    )


# ── Override helpers ──────────────────────────────────────────────────────────

def override_current_user(role: Role = Role.UNDERWRITER):
    async def _get_user():
        return make_user(role)
    return _get_user


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client() -> TestClient:
    """TestClient with authenticated UNDERWRITER user."""
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user(Role.UNDERWRITER)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def admin_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user(Role.ADMIN)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def unauth_client() -> TestClient:
    """Client without any auth override (raw app)."""
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_token
from app.models.domain.user import Role, UserInDB
from app.repositories.user_repository import UserRepository, get_user_repository

settings = get_settings()
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserInDB:
    if credentials is None:
        raise AuthenticationError("Missing bearer token")
    try:
        payload = decode_token(credentials.credentials)
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc

    if payload.get("type") != "access":
        raise AuthenticationError("Expected access token")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token missing subject claim")

    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthenticationError("User account is disabled")
    return user


def require_roles(*roles: Role):
    """Factory that returns a dependency enforcing one of the given roles."""

    async def _check(
        current_user: Annotated[UserInDB, Depends(get_current_user)],
    ) -> UserInDB:
        if current_user.role not in roles:
            raise AuthorizationError(
                f"Required roles: {[r.value for r in roles]}. "
                f"Your role: {current_user.role.value}"
            )
        return current_user

    return _check


# ── Idempotency ───────────────────────────────────────────────────────────────


async def get_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    return idempotency_key

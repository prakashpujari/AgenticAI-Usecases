from __future__ import annotations

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.domain.user import UserInDB
from app.models.requests.auth import LoginRequest
from app.models.responses.auth import TokenResponse
from app.repositories.user_repository import UserRepository

settings = get_settings()


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._repo = user_repo

    async def login(self, request: LoginRequest) -> TokenResponse:
        user = await self._repo.get_by_username(request.username)
        if user is None or not verify_password(request.password, user.hashed_password):
            raise AuthenticationError("Invalid username or password")
        if not user.is_active:
            raise AuthenticationError("Account is disabled")

        extra = {"role": user.role.value, "email": user.email}
        access = create_access_token(subject=user.id, extra_claims=extra)
        refresh = create_refresh_token(subject=user.id)

        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        from jose import JWTError

        try:
            payload = decode_token(refresh_token)
        except JWTError as exc:
            raise AuthenticationError("Invalid or expired refresh token") from exc

        if payload.get("type") != "refresh":
            raise AuthenticationError("Not a refresh token")

        user_id: str | None = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Token missing subject claim")

        user = await self._repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("User not found or disabled")

        extra = {"role": user.role.value, "email": user.email}
        access = create_access_token(subject=user.id, extra_claims=extra)
        new_refresh = create_refresh_token(subject=user.id)

        return TokenResponse(
            access_token=access,
            refresh_token=new_refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )

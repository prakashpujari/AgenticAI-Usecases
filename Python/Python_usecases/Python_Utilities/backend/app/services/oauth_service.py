from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
from jose import JWTError
from jose import jwt as jose_jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, create_refresh_token
from app.models.domain.user import Role, UserInDB
from app.repositories.user_repository import UserRepository


class OAuthService:
    """Validates external OAuth/OIDC tokens (Google, Cognito) and provisions local users."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._repo = user_repo
        self._settings = get_settings()

    # ── Google ────────────────────────────────────────────────────────────────

    async def authenticate_google(self, id_token: str) -> dict[str, Any]:
        """Validate a Google ID token and return our JWT pair."""
        if not self._settings.google_client_id:
            raise AuthenticationError("Google OAuth is not configured on this server")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://www.googleapis.com/oauth2/v3/certs")
            resp.raise_for_status()
            jwks = resp.json()

        try:
            claims: dict[str, Any] = jose_jwt.decode(
                id_token,
                jwks,
                algorithms=["RS256"],
                audience=self._settings.google_client_id,
                options={"verify_at_hash": False},
            )
        except JWTError as exc:
            raise AuthenticationError(f"Invalid Google token: {exc}") from exc

        return await self._provision_and_issue(
            external_id=f"google_{claims['sub']}",
            email=claims.get("email", ""),
            name=claims.get("name", claims.get("email", "Google User")),
        )

    # ── Cognito ───────────────────────────────────────────────────────────────

    def get_cognito_authorize_url(self, state: str, code_challenge: str) -> str:
        """Build the Cognito Hosted UI authorization URL (PKCE / S256)."""
        settings = self._settings
        if not settings.cognito_domain or not settings.cognito_client_id:
            raise AuthenticationError("Cognito OAuth is not configured on this server")

        params = urlencode(
            {
                "response_type": "code",
                "client_id": settings.cognito_client_id,
                "redirect_uri": settings.oauth_redirect_uri,
                "scope": "openid email profile",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"https://{settings.cognito_domain}/oauth2/authorize?{params}"

    async def exchange_cognito_code(self, code: str, code_verifier: str) -> dict[str, Any]:
        """Exchange a Cognito authorization code for our JWT pair."""
        settings = self._settings
        if not settings.cognito_domain or not settings.cognito_client_id:
            raise AuthenticationError("Cognito OAuth is not configured on this server")

        token_url = f"https://{settings.cognito_domain}/oauth2/token"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.cognito_client_id,
                    "code": code,
                    "redirect_uri": settings.oauth_redirect_uri,
                    "code_verifier": code_verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise AuthenticationError(
                    f"Cognito token exchange failed: {resp.text}"
                ) from exc
            tokens = resp.json()

        id_token: str = tokens.get("id_token", "")
        if not id_token:
            raise AuthenticationError("Cognito did not return an id_token")

        return await self._validate_cognito_id_token(id_token)

    async def _validate_cognito_id_token(self, id_token: str) -> dict[str, Any]:
        settings = self._settings
        region = settings.cognito_region
        pool_id = settings.cognito_user_pool_id
        jwks_url = (
            f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            jwks = resp.json()

        try:
            claims: dict[str, Any] = jose_jwt.decode(
                id_token,
                jwks,
                algorithms=["RS256"],
                audience=settings.cognito_client_id,
            )
        except JWTError as exc:
            raise AuthenticationError(f"Invalid Cognito token: {exc}") from exc

        return await self._provision_and_issue(
            external_id=f"cognito_{claims['sub']}",
            email=claims.get("email", ""),
            name=claims.get("name", claims.get("email", "Cognito User")),
        )

    # ── Shared ────────────────────────────────────────────────────────────────

    async def _provision_and_issue(
        self, external_id: str, email: str, name: str
    ) -> dict[str, Any]:
        """Find or create a local user and issue our JWT pair."""
        if not email:
            raise AuthenticationError("Identity provider did not supply an email address")

        user = await self._repo.get_by_email(email)
        if user is None:
            user = UserInDB(
                id=external_id,
                username=email,
                email=email,
                full_name=name,
                hashed_password="",  # OAuth users have no local password
                role=Role.OPS,  # default role; admins can elevate later
                is_active=True,
            )
            await self._repo.save(user)

        extra = {"role": user.role.value, "email": user.email}
        access = create_access_token(subject=user.id, extra_claims=extra)
        refresh = create_refresh_token(subject=user.id)
        settings = self._settings
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        }

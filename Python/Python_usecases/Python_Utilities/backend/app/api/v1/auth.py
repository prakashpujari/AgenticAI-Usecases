from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.models.requests.auth import LoginRequest, RefreshRequest
from app.models.responses.auth import TokenResponse, UserResponse
from app.repositories.user_repository import UserRepository, get_user_repository
from app.services.auth_service import AuthService
from app.services.oauth_service import OAuthService
from app.core.dependencies import get_current_user
from app.models.domain.user import UserInDB

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── OAuth request models ──────────────────────────────────────────────────────

class GoogleTokenRequest(BaseModel):
    id_token: str  # Google ID token from @react-oauth/google


class CognitoCallbackRequest(BaseModel):
    code: str         # Authorization code from Cognito redirect
    code_verifier: str  # PKCE code verifier (stored client-side before redirect)


def _auth_service(repo: Annotated[UserRepository, Depends(get_user_repository)]) -> AuthService:
    return AuthService(repo)


def _oauth_service(repo: Annotated[UserRepository, Depends(get_user_repository)]) -> OAuthService:
    return OAuthService(repo)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Obtain access and refresh tokens",
    description="Authenticate with username/password and receive JWT access + refresh tokens.",
)
async def login(
    request: LoginRequest,
    service: Annotated[AuthService, Depends(_auth_service)],
) -> TokenResponse:
    return await service.login(request)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access/refresh token pair.",
)
async def refresh_token(
    request: RefreshRequest,
    service: Annotated[AuthService, Depends(_auth_service)],
) -> TokenResponse:
    return await service.refresh(request.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
    )


# ── OAuth endpoints ───────────────────────────────────────────────────────────

@router.post(
    "/oauth/google",
    response_model=TokenResponse,
    summary="Sign in with Google",
    description=(
        "Validate a Google ID token (from Google Identity Services / @react-oauth/google) "
        "and return platform access + refresh tokens. A new user account is auto-provisioned "
        "on first sign-in with OPS role."
    ),
)
async def google_login(
    request: GoogleTokenRequest,
    service: Annotated[OAuthService, Depends(_oauth_service)],
) -> dict[str, Any]:
    return await service.authenticate_google(request.id_token)


@router.get(
    "/oauth/cognito/authorize",
    summary="Get Cognito Hosted UI authorization URL",
    description=(
        "Returns the Cognito Hosted UI URL for starting an OAuth 2.0 PKCE authorization flow. "
        "The frontend redirects the user to this URL, then handles the callback at /auth/callback."
    ),
)
async def cognito_authorize_url(
    state: str = Query(..., description="Random CSRF state value"),
    code_challenge: str = Query(..., description="PKCE SHA-256 code challenge (base64url)"),
    service: OAuthService = Depends(_oauth_service),
) -> dict[str, str]:
    url = service.get_cognito_authorize_url(state=state, code_challenge=code_challenge)
    return {"url": url}


@router.post(
    "/oauth/cognito/callback",
    response_model=TokenResponse,
    summary="Exchange Cognito authorization code for platform tokens",
    description=(
        "Complete the Cognito PKCE flow: exchange the authorization code and PKCE "
        "code_verifier for platform access + refresh tokens."
    ),
)
async def cognito_callback(
    request: CognitoCallbackRequest,
    service: Annotated[OAuthService, Depends(_oauth_service)],
) -> dict[str, Any]:
    return await service.exchange_cognito_code(
        code=request.code, code_verifier=request.code_verifier
    )

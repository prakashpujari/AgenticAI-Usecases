from __future__ import annotations

from pydantic import BaseModel

from app.models.domain.user import Role


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    role: Role
    is_active: bool

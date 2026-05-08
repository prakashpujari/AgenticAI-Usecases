from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field


class Role(StrEnum):
    UNDERWRITER = "UNDERWRITER"
    OPS = "OPS"
    ADMIN = "ADMIN"
    READ_ONLY = "READ_ONLY"


class UserInDB(BaseModel):
    """Internal representation stored in the repository (includes hashed password)."""

    id: str
    username: str
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool = True
    hashed_password: str = Field(exclude=True)  # never serialise

    model_config = {"from_attributes": True}

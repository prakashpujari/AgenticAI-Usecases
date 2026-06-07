from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from app.core.config import settings

security = HTTPBearer()


class RunUser(BaseModel):
    user_id: str
    email: str
    roles: list[str]
    gitlab_username: str | None = None


class AuthService:
    @staticmethod
    async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> RunUser:
        token = credentials.credentials
        try:
            payload = jwt.decode(token, "PLACEHOLDER_SECRET", algorithms=["HS256"])
            return RunUser(
                user_id=payload.get("sub"),
                email=payload.get("email"),
                roles=payload.get("roles", ["Viewer"]),
                gitlab_username=payload.get("gitlab_username"),
            )
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")

    @staticmethod
    def require_role(user: RunUser, allowed_roles: list[str]) -> None:
        if not any(role in allowed_roles for role in user.roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

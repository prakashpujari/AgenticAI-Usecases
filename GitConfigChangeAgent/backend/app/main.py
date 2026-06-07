from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.telemetry import configure_telemetry
from jose import jwt
from datetime import datetime, timedelta

configure_logging()
configure_telemetry()

app = FastAPI(
    title="GitConfigChangeAgent API",
    version="0.1.0",
    description="API for agentic GitLab configuration change orchestration.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/healthz")
async def health_check():
    return {"status": "ok"}

@app.post("/dev/auth/token")
async def dev_token():
    """Development endpoint: issues a test JWT token for local testing."""
    payload = {
        "sub": "dev-user",
        "email": "dev@localhost",
        "roles": ["Admin"],
        "gitlab_username": "dev-user",
        "exp": datetime.utcnow() + timedelta(days=1)
    }
    token = jwt.encode(payload, "PLACEHOLDER_SECRET", algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}

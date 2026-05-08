from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "Mortgage Utilities Platform"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # ── API ───────────────────────────────────────────────────────────────────
    api_v1_prefix: str = "/api/v1"

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = Field(default="dev_secret_change_in_prod_min_32_chars_xx", min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003", "http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_socket_timeout: float = 2.0
    redis_socket_connect_timeout: float = 2.0

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 20

    # ── AI Provider ───────────────────────────────────────────────────────────
    ai_provider: Literal["mock", "openai", "bedrock", "azure_openai"] = "mock"
    ai_request_timeout: float = 30.0
    openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_key: str | None = None
    azure_openai_deployment: str | None = None

    # ── Observability ─────────────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str | None = None
    log_level: str = "INFO"

    # ── Circuit Breaker ───────────────────────────────────────────────────────
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60

    # ── Idempotency ───────────────────────────────────────────────────────────
    idempotency_ttl_seconds: int = 86_400  # 24 h

    # ── OAuth / Cognito ───────────────────────────────────────────────────────
    cognito_region: str = "us-east-1"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_domain: str = ""  # e.g. my-app.auth.us-east-1.amazoncognito.com
    google_client_id: str = ""
    oauth_redirect_uri: str = "http://localhost:3000/auth/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()

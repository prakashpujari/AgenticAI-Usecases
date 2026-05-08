"""
Application configuration using Pydantic Settings.
All values can be overridden via environment variables or .env file.
"""
from __future__ import annotations

from typing import List, Literal, Optional
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Override any system/shell env vars with values from .env so the project's
# .env file is always the authoritative source of configuration.
load_dotenv(override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── OpenAI ───────────────────────────────────────────────────────────
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field("gpt-4o", description="Chat completion model")
    openai_embedding_model: str = Field(
        "text-embedding-3-small", description="Embedding model"
    )

    # ── Pinecone ─────────────────────────────────────────────────────────
    pinecone_api_key: str = Field(..., description="Pinecone API key")
    pinecone_index_name: str = Field("jira-issues", description="Pinecone index name")
    pinecone_environment: str = Field("us-east-1", description="Pinecone region")
    pinecone_dimension: int = Field(1536, description="Embedding dimension")
    pinecone_host: Optional[str] = Field(None, description="Pinecone index host URL (bypasses control plane lookup)")

    # ── Redis ────────────────────────────────────────────────────────────
    redis_url: str = Field("redis://localhost:6379", description="Redis connection URL")
    redis_ttl: int = Field(86400, description="Default cache TTL in seconds (24h)")

    # ── Jira ─────────────────────────────────────────────────────────────
    jira_base_url: str = Field(..., description="Jira Cloud base URL (e.g. https://myorg.atlassian.net)")
    jira_email: str = Field(..., description="Jira account email for Basic Auth")
    jira_api_token: str = Field(..., description="Jira API token for Basic Auth")
    jira_default_project: str = Field("PROJ", description="Default Jira project key")

    @field_validator("jira_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    # ── LangSmith ────────────────────────────────────────────────────────
    langchain_api_key: Optional[str] = Field(None, description="LangSmith API key")
    langchain_endpoint: str = Field(
        "https://api.smith.langchain.com", description="LangSmith API endpoint"
    )
    langchain_tracing_v2: bool = Field(True, description="Enable LangSmith tracing")
    langchain_project: str = Field(
        "jira-automation-agent", description="LangSmith project name"
    )

    # ── RBAC / Governance ────────────────────────────────────────────────
    # Accepts a comma-separated env var: ALLOWED_PROJECTS=PROJ,INFRA,PLATFORM
    allowed_projects: List[str] = Field(
        default=["PROJ", "INFRA", "PLATFORM"],
        description="Allowed Jira project keys (comma-separated in env)",
    )

    @field_validator("allowed_projects", mode="before")
    @classmethod
    def parse_csv_projects(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json as _json
                return _json.loads(v)
            return [p.strip() for p in v.split(",") if p.strip()]
        return v

    allowed_priorities: List[str] = Field(
        default=["P0", "P1", "P2", "P3"],
        description="Valid priority values",
    )
    allowed_issue_types: List[str] = Field(
        default=["Epic", "Story", "Bug", "Task", "Sub-task"],
        description="Valid Jira issue types",
    )

    # ── Agent Control ────────────────────────────────────────────────────
    max_review_iterations: int = Field(
        2, description="Maximum agent review/refine iterations"
    )
    rag_top_k: int = Field(10, description="RAG retrieval top-K")
    dedupe_threshold: float = Field(0.90, description="Dedupe similarity threshold")

    # ── Server / Deployment ──────────────────────────────────────────────
    # Set ENVIRONMENT=production in prod. Controls Swagger UI visibility,
    # log format, and CORS strictness.
    environment: Literal["development", "production"] = Field(
        "development", description="Runtime environment"
    )

    # Comma-separated allowed CORS origins.
    # Dev default allows both CRA and Vite dev servers.
    # In production, set CORS_ORIGINS=https://your-domain.com
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins (comma-separated in env)",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json as _json
                return _json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # Rate limiting: requests per minute per IP for /ai/* endpoints.
    api_rate_limit: int = Field(30, description="Max requests/minute per IP on /ai/* endpoints")

    # Maximum request body size in bytes (10 MB default).
    max_body_size: int = Field(10 * 1024 * 1024, description="Max request body size in bytes")


settings = Settings()

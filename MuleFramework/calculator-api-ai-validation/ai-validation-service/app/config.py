"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev")
    log_level: str = Field(default="INFO")

    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    # Comma-separated list of fallback models tried in order when the primary
    # model returns 429 / 503 / 529 or a network error.
    groq_fallback_models: str = Field(
        default=(
            "llama-3.1-8b-instant,"
            "meta-llama/llama-4-scout-17b-16e-instruct,"
            "moonshotai/kimi-k2-instruct"
        )
    )
    groq_temperature: float = Field(default=0.2)
    groq_max_tokens: int = Field(default=1024)
    groq_timeout_seconds: float = Field(default=30.0)

    munit_reports_dir: Path = Field(default=Path("./sample_reports"))
    raml_path: Path = Field(default=Path("./fixtures/raml/calculator-api.raml"))
    mule_xml_dir: Path = Field(default=Path("./fixtures/mule"))

    # LangSmith tracing
    langchain_tracing_v2: str = Field(default="false")
    langchain_api_key: str = Field(default="")
    langchain_project: str = Field(default="mule-ai-validation")
    langchain_endpoint: str = Field(default="https://api.smith.langchain.com")


@lru_cache
def get_settings() -> Settings:
    return Settings()

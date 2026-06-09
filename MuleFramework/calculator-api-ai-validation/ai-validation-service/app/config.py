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
    groq_fallback_model: str = Field(default="llama-3.1-8b-instant")
    groq_temperature: float = Field(default=0.2)
    groq_max_tokens: int = Field(default=1024)
    groq_timeout_seconds: float = Field(default=30.0)

    munit_reports_dir: Path = Field(default=Path("./sample_reports"))
    raml_path: Path = Field(default=Path("./fixtures/raml/calculator-api.raml"))
    mule_xml_dir: Path = Field(default=Path("./fixtures/mule"))


@lru_cache
def get_settings() -> Settings:
    return Settings()

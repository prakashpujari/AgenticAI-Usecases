from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    gitlab_base_url: str
    gitlab_token: str
    groq_api_key: str
    pinecone_api_key: str
    pinecone_environment: str
    pinecone_index: str
    postgres_dsn: str
    langsmith_api_key: str
    cors_allow_origins: list[str] = ["*"]
    opentelemetry_otlp_endpoint: str | None = None
    app_name: str = "gitconfigchangeagent"
    app_version: str = "0.1.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

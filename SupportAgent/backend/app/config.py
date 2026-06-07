import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App Configuration
    app_name: str = "AIOps Platform"
    app_version: str = "1.0.0"
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = environment == "development"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # API Configuration
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_prefix: str = "/api/v1"
    cors_origins: list = ["*"]

    # Database Configuration
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://aiops:aiops@localhost:5432/aiops_db"
    )
    db_echo: bool = debug
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    # Redis Configuration
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_db: int = 0
    cache_ttl: int = 3600  # 1 hour default
    cache_enabled: bool = True

    # Milvus Configuration
    milvus_host: str = os.getenv("MILVUS_HOST", "localhost")
    milvus_port: int = int(os.getenv("MILVUS_PORT", "19530"))
    milvus_collection_name: str = "aiops_knowledge_base"
    milvus_embedding_dim: int = 1536

    # LLM Configuration (Claude via Anthropic)
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    llm_model: str = "claude-3-sonnet-20240229"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048
    langsmith_api_key: Optional[str] = os.getenv("LANGSMITH_API_KEY")
    langsmith_project: str = "aiops-platform"

    # Splunk Configuration
    splunk_host: str = os.getenv("SPLUNK_HOST", "localhost")
    splunk_port: int = int(os.getenv("SPLUNK_PORT", "8089"))
    splunk_username: str = os.getenv("SPLUNK_USERNAME", "admin")
    splunk_password: str = os.getenv("SPLUNK_PASSWORD", "")
    splunk_index: str = os.getenv("SPLUNK_INDEX", "main")

    # Datadog Configuration
    datadog_api_key: str = os.getenv("DATADOG_API_KEY", "")
    datadog_app_key: str = os.getenv("DATADOG_APP_KEY", "")
    datadog_api_url: str = os.getenv("DATADOG_API_URL", "https://api.datadoghq.com")

    # Prometheus Configuration
    prometheus_url: str = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    prometheus_query_timeout: int = 30

    # ServiceNow Configuration
    servicenow_instance: str = os.getenv("SERVICENOW_INSTANCE", "")
    servicenow_username: str = os.getenv("SERVICENOW_USERNAME", "")
    servicenow_password: str = os.getenv("SERVICENOW_PASSWORD", "")
    servicenow_api_url: str = os.getenv(
        "SERVICENOW_API_URL",
        f"https://{servicenow_instance}.service-now.com/api/now"
    )

    # Jira Configuration
    jira_server: str = os.getenv("JIRA_SERVER", "")
    jira_username: str = os.getenv("JIRA_USERNAME", "")
    jira_api_token: str = os.getenv("JIRA_API_TOKEN", "")
    jira_project_key: str = os.getenv("JIRA_PROJECT_KEY", "OPS")

    # Notification Configuration
    slack_webhook_url: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")
    teams_webhook_url: Optional[str] = os.getenv("TEAMS_WEBHOOK_URL")
    email_smtp_server: Optional[str] = os.getenv("EMAIL_SMTP_SERVER")
    email_from: Optional[str] = os.getenv("EMAIL_FROM")

    # ML Model Configuration
    ml_model_path: str = os.getenv("ML_MODEL_PATH", "./models")
    isolation_forest_contamination: float = 0.05
    lstm_lookback_window: int = 24  # hours
    lstm_prediction_horizon: int = 1  # hour ahead
    anomaly_detection_enabled: bool = True

    # Incident Configuration
    incident_confidence_threshold: float = 0.85
    auto_remediation_p3_p4: bool = True
    incident_severity_thresholds: dict = {
        "p1": 0.95,
        "p2": 0.85,
        "p3": 0.70,
        "p4": 0.50
    }

    # Agent Configuration
    max_agent_iterations: int = 10
    agent_timeout: int = 300  # 5 minutes
    enable_agent_tracing: bool = True

    # Security Configuration
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")
    pii_redaction_enabled: bool = True
    audit_logging_enabled: bool = True
    enable_rbac: bool = True
    enable_abac: bool = True

    # OpenTelemetry Configuration
    otel_enabled: bool = True
    otel_exporter: str = os.getenv("OTEL_EXPORTER", "jaeger")
    jaeger_host: str = os.getenv("JAEGER_HOST", "localhost")
    jaeger_port: int = int(os.getenv("JAEGER_PORT", "6831"))

    # Cloud Configuration
    cloud_provider: str = os.getenv("CLOUD_PROVIDER", "aws")  # aws, gcp, azure
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")
    azure_subscription_id: str = os.getenv("AZURE_SUBSCRIPTION_ID", "")

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 1000
    rate_limit_window: int = 3600  # 1 hour

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

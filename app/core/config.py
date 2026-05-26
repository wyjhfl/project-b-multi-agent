from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "project-b-multi-agent"
    app_env: str = "development"
    debug: bool = True
    cors_enabled: bool = True
    cors_allow_origins: str = "http://localhost:3000"
    cors_allow_credentials: bool = True
    cors_allow_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_allow_headers: str = "Authorization,Content-Type"
    security_headers_enabled: bool = True
    rate_limit_enabled: bool = False
    rate_limit_requests_per_minute: int = 120
    rate_limit_burst: int = 60
    rate_limit_exempt_paths: str = "/health"
    request_size_limit_enabled: bool = True
    request_size_limit_bytes: int = 1048576
    abuse_guard_enabled: bool = True
    structured_logging_enabled: bool = True
    log_level: str = "INFO"
    log_include_client_ip: bool = True
    log_include_user_agent: bool = True
    log_redaction_enabled: bool = True
    audit_retention_enabled: bool = True
    audit_retention_days: int = 90
    audit_export_enabled: bool = True
    audit_export_max_rows: int = 1000
    audit_export_format: str = "jsonl"
    audit_export_redaction_enabled: bool = True
    ops_db_path: str = "data/db/ops_demo.sqlite"
    runtime_db_path: str = "data/db/runtime.sqlite"
    metrics_db_path: str = "data/db/runtime_metrics.sqlite"

    nl2sql_generator: str = "mock"
    llm_provider: str = "fake"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_timeout_seconds: float = 15.0
    llm_max_retries: int = 0
    llm_retry_backoff_seconds: float = 0.5
    llm_temperature: float = 0.0
    judge_provider: str = "fake"
    judge_fallback_to_fake: bool = True
    judge_model: str = ""
    judge_base_url: str = ""
    judge_timeout_seconds: float = 15.0
    judge_max_retries: int = 0
    judge_retry_backoff_seconds: float = 0.5
    llm_budget_enabled: bool = False
    llm_budget_soft_usd: float = 0.0
    llm_budget_hard_usd: float = 0.0
    llm_budget_scope: str = "daily"
    llm_cache_enabled: bool = False
    llm_cache_ttl_seconds: int = 3600
    real_llm_acceptance_enabled: bool = False
    real_llm_preflight_enabled: bool = False
    real_llm_provider: str = "litellm"
    real_llm_model: str = ""
    real_llm_base_url: str = ""
    real_llm_api_key_env: str = "OPENAI_API_KEY"
    real_llm_preflight_timeout_seconds: float = 10.0
    real_llm_preflight_network_check: bool = False
    real_llm_smoke_enabled: bool = False

    mcp_mode: str = "fake"
    mcp_server_name: str = "fake_ops_mcp"
    mcp_server_command: str = ""
    mcp_server_args: str = ""
    mcp_server_timeout_seconds: float = 10.0
    mcp_server_workdir: str = ""
    mcp_server_env_allowlist: str = ""
    mcp_server_command_allowlist: str = ""

    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-only-change-me-please-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    auth_enabled: bool = False
    rbac_enabled: bool = False
    storage_backend: str = "sqlite"
    redis_enabled: bool = False
    graph_runtime_enabled: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()

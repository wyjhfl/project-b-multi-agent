from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "project-b-multi-agent"
    app_env: str = "development"
    debug: bool = True
    ops_db_path: str = "data/db/ops_demo.sqlite"
    runtime_db_path: str = "data/db/runtime.sqlite"
    metrics_db_path: str = "data/db/runtime_metrics.sqlite"

    nl2sql_generator: str = "mock"
    llm_provider: str = "fake"
    llm_model: str = ""
    llm_api_key: str = ""

    mcp_mode: str = "fake"
    mcp_server_name: str = "fake_ops_mcp"
    mcp_server_command: str = ""
    mcp_server_args: str = ""
    mcp_server_timeout_seconds: float = 10.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

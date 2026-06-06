# v4.4 Real Integration Env Profile Checker

## 目的

`scripts/real_integration_env_profile.py` 用于只读检查 v4.4 真实集成相关环境配置。它对比 `.env.example` 与 `.env.production.example` 的模板键名和占位状态，并补充当前进程环境中的 opt-in present 布尔。

## 覆盖域

- `real_llm`
- `postgres`
- `redis`
- `external_mcp`
- `staging_smoke`

## 关键配置

- real LLM：`REAL_LLM_PREFLIGHT_ENABLED`、`REAL_LLM_ACCEPTANCE_ENABLED`、`REAL_LLM_SMOKE_ENABLED`、`REAL_LLM_PROVIDER`、`REAL_LLM_MODEL`、`REAL_LLM_BASE_URL`、`REAL_LLM_API_KEY_ENV`、`REAL_LLM_PREFLIGHT_TIMEOUT_SECONDS`、`REAL_LLM_PREFLIGHT_NETWORK_CHECK`
- PostgreSQL：`STORAGE_BACKEND`、`DATABASE_URL`
- Redis：`REDIS_ENABLED`、`REDIS_URL`、`RATE_LIMIT_BACKEND`
- external MCP：`MCP_MODE`、`MCP_SERVER_COMMAND`、`MCP_SERVER_COMMAND_ALLOWLIST`、`MCP_TOOL_ALLOWLIST`、`MCP_SERVER_ENV_ALLOWLIST`、`MCP_SERVER_TIMEOUT_SECONDS`
- staging smoke：`REAL_INTEGRATION_STAGING_SMOKE_ENABLED`、`REAL_LLM_STAGING_SMOKE_EXECUTE`、`POSTGRES_STAGING_SMOKE_EXECUTE`、`REDIS_STAGING_SMOKE_EXECUTE`、`MCP_STAGING_SMOKE_EXECUTE`

## 只读边界

- 不连接真实 LLM、PostgreSQL、Redis 或 external MCP Server。
- 不执行 Alembic migration。
- 不写业务、审计或指标数据。
- 不读取或输出 secret 原文。
- `REAL_LLM_API_KEY_ENV` 只检查其指向的目标环境变量是否存在，不读取目标值。
- 模板 literal 值只输出 `[literal]` 状态，不输出原值。
- secret-like 占位值只输出 placeholder/redacted 状态；secret-like 非占位值触发 `blocked`。

以下输出字段默认始终为 `false`：

- `real_llm_executed`
- `database_connected`
- `redis_connected`
- `external_mcp_connected`
- `migration_executed`
- `business_data_written`
- `audit_data_written`
- `metrics_data_written`
- `secret_plaintext_output`

## 状态语义

- `skipped`：缺少模板关键键，或当前 env opt-in 条件缺失。
- `partial`：模板关键键齐备且当前 opt-in 条件齐备，但脚本仍只做只读检查，不执行真实连接。
- `blocked`：发现模板值或输出中存在 secret-like 原文风险。

## 输出

默认输出目录：

- `docs/reports/real_integration_env_profile/`

交付物：

- `scripts/real_integration_env_profile.py`
- `tests/test_real_integration_env_profile_v444.py`

## 使用方式

```bash
python -m scripts.real_integration_env_profile
python -m scripts.real_integration_env_profile --output-dir docs/reports/real_integration_env_profile
```

测试：

```bash
python -m pytest tests/test_real_integration_env_profile_v444.py
```

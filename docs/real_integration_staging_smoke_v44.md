# v4.4 真实集成 Staging Smoke（受控入口）

## 目标

`scripts/real_integration_staging_smoke.py` 提供真实 LLM、PostgreSQL、Redis 与 external MCP 的统一 staging smoke 编排入口。默认只生成 dry-run 证据，不连接真实外部系统。

## 执行门禁

真实执行必须同时满足：

- 命令行传入 `--execute`。
- `REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true`。
- 单域执行开关开启：
  - `REAL_LLM_STAGING_SMOKE_EXECUTE=true`
  - `POSTGRES_STAGING_SMOKE_EXECUTE=true`
  - `REDIS_STAGING_SMOKE_EXECUTE=true`
  - `MCP_STAGING_SMOKE_EXECUTE=true`
- 单域 opt-in 配置完整。

默认不满足这些条件时，脚本只输出 `skipped` 或 `blocked` 证据，不调用执行器。

可通过 `--domains` 只执行指定域，便于分批接入：

```powershell
python scripts/real_integration_staging_smoke.py --execute --domains postgres
python scripts/real_integration_staging_smoke.py --execute --domains real_llm,external_mcp
```

未指定 `--domains` 时默认覆盖 `real_llm,postgres,redis,external_mcp` 四个域。非法域会触发 `blocked`，不会调用执行器。

## 默认执行器

当真实执行门禁满足时，默认执行器执行最小 smoke：

- `real_llm`：调用 `run_llm_provider_preflight(perform_network_check=True)`，只记录 provider、model 是否存在、API key env 名称、网络检查是否执行、latency 和错误数量，不输出 API key。
- `postgres`：调用 `check_database_health()`，只记录 `status`、`backend` 和是否存在错误，不输出 `DATABASE_URL`。
- `redis`：调用 `check_redis_health()`，只记录 `status`、`backend` 和是否存在错误，不输出 `REDIS_URL`。
- `external_mcp`：使用 `StdioMCPClient.list_tools()` 做最小 discovery smoke，随后关闭进程；只记录工具数量、初始化状态和 failure_count，不输出 command 原文或 secret。

## 边界

- 默认不调用真实 LLM。
- 默认不连接 PostgreSQL。
- 默认不连接 Redis。
- 默认不启动或连接真实 MCP Server。
- 不执行 Alembic migration。
- 不写业务/审计/指标数据。
- 不读取或输出 secret、token、API key、`DATABASE_URL`、`REDIS_URL` 或 MCP command 原文。
- `public_production_direct_launch` 始终为 `No-Go`。

## 输出

默认输出目录：`docs/reports/real_integration_staging_smoke/`。

输出 JSON 与 Markdown，包含：

- 四个域的 `status`
- `execution_allowed`
- `execution_invoked`
- `missing_conditions`
- 顶层执行标志：`real_llm_executed`、`database_connected`、`redis_connected`、`external_mcp_connected`

该报告会被 `real_integration_staging_gate.py` 和 `real_integration_gap_register.py` 消费。

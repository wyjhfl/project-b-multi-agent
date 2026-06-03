# v3.7 Phase 17.1 External integration baseline inventory

## 目标

Phase 17.1 建立真实外部集成与 provider 验收前的只读基线盘点，覆盖 external MCP、real LLM provider、LLM judge、PostgreSQL、Redis、deployment guard、tool approval audit 和 frontend offline build。

本阶段只读，不连接真实外部系统，不调用真实外网 LLM，不读取或输出真实 secret 原文。

## 入口

```powershell
python scripts/external_provider_acceptance_inventory.py
```

可指定输出目录：

```powershell
python scripts/external_provider_acceptance_inventory.py --output-dir docs/reports/external_provider_acceptance_inventory/
```

默认输出：

- JSON：`docs/reports/external_provider_acceptance_inventory/*_external_provider_acceptance_inventory.json`
- Markdown：`docs/reports/external_provider_acceptance_inventory/*_external_provider_acceptance_inventory.md`

## 输出范围

- `external_mcp`：MCP_MODE、MCP_SERVER_COMMAND、allowlist、本地 stdio client 与 fake fixture。
- `real_llm_provider`：REAL_LLM_* opt-in 条件、API key env name 与 target present 布尔状态。
- `llm_judge_provider`：judge provider、eval 入口和真实 judge smoke 边界。
- `postgres_store`：STORAGE_BACKEND、DATABASE_URL present、Alembic 与 prod compose。
- `redis_runtime`：REDIS_ENABLED、REDIS_URL present、Noop fallback 边界。
- `deployment_guard`：deployment guard、本地/prod compose、配置门禁。
- `tool_approval_audit`：ToolGateway、PolicyEngine、approval、audit 入口。
- `frontend_offline_build`：前端 package、layout、globals、本地系统字体栈。

## 状态语义

- `partial`：本地工程基础存在，但缺少真实 opt-in 或生产验收证据。
- `skipped`：缺少必需配置或本地文件。
- `blocked`：发现真实 secret 原文输出风险、真实外部调用已执行或只读边界被破坏。
- `success`：保留给后续真实 opt-in 验收完成并形成脱敏证据后使用。

## 只读边界

- 不连接真实外部 MCP。
- 不调用真实外网 LLM。
- 不连接真实业务系统。
- 不执行真实数据库迁移或 Redis 写入。
- 不读取或输出真实 secret 原文。
- 不绕过后端 ToolGateway、PolicyEngine、审批链路或审计链路。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- 不宣称真实 provider 或真实业务系统生产验收完成。

## 验证

```powershell
python -m pytest tests/test_external_provider_acceptance_inventory_v371.py -q
python -m pytest tests/test_mcp_stdio_client_v31.py tests/test_llm_provider_v41.py tests/test_storage_v20.py -q
docker compose config
```

## 后续衔接

- Phase 17.2：External MCP acceptance gate。
- Phase 17.3：Real LLM provider acceptance gate。

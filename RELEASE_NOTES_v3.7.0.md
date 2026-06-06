# v3.7.0 发布说明

## 摘要

v3.7.0 = **External Integration & Real Provider Acceptance**。

本轮 release prep 汇总 Phase 17.1~17.5 的真实外部集成与 provider 受控验收准备能力，覆盖 external MCP、real LLM provider、PostgreSQL/Redis、业务系统集成安全清单和证据边界。当前仍为只读门禁与受控验收准备，不等于真实外部 MCP、真实 LLM、PostgreSQL、Redis 或业务系统生产验收完成。

## 阶段覆盖

### Phase 17.1 - External integration baseline inventory

- 新增 `docs/external_provider_acceptance_inventory_v37.md`。
- 新增 `scripts/external_provider_acceptance_inventory.py` 与 `tests/test_external_provider_acceptance_inventory_v371.py`。
- 只读盘点 external MCP、real LLM provider、LLM judge、PostgreSQL、Redis、deployment guard、tool approval audit 和 frontend offline build。
- 输出 `read_only=true`、`real_llm_executed=false`、`external_mcp_connected=false`、`business_system_connected=false`。

### Phase 17.2 - External MCP acceptance gate

- 新增 `docs/external_mcp_acceptance_gate_v37.md`。
- 新增 `scripts/external_mcp_acceptance_gate.py` 与 `tests/test_external_mcp_acceptance_gate_v372.py`。
- 只读复核 real mode opt-in、command allowlist、tool allowlist、timeout、lifecycle hardening、approval/audit boundary 和 fake fixture coverage。
- 不启动 MCP subprocess，不执行真实 `tools/list` 或 `tools/call`。

### Phase 17.3 - Real LLM provider acceptance gate

- 新增 `docs/real_llm_provider_acceptance_gate_v37.md`。
- 新增 `scripts/real_llm_provider_acceptance_gate.py` 与 `tests/test_real_llm_provider_acceptance_gate_v373.py`。
- 只读复核 preflight、network check gate、smoke opt-in、budget/cache/fallback、PII/prompt guardrails、report redaction、judge acceptance 和 evidence index。
- 不调用真实外网 LLM，不执行 provider network check，不读取 pilot report 正文。

### Phase 17.4 - Store and Redis production readiness drill

- 新增 `docs/store_redis_readiness_drill_v37.md`。
- 新增 `scripts/store_redis_readiness_drill.py` 与 `tests/test_store_redis_readiness_drill_v374.py`。
- 只读复核 PostgreSQL Store opt-in、Store Factory、SQLite fallback、Alembic migration precheck、Redis opt-in、NoopRedisClient fallback、进程内限流边界、deployment guard、审计/指标 store 边界和 compose readiness。
- 不连接真实 PostgreSQL/Redis，不执行 Alembic migration，不写业务/审计/指标数据。

### Phase 17.5 - Business system integration safety checklist

- 新增 `docs/business_system_integration_safety_checklist_v37.md`。
- 新增 `scripts/business_system_integration_safety_checklist.py` 与 `tests/test_business_system_integration_safety_checklist_v375.py`。
- 只读复核业务系统 opt-in、secret target、ToolGateway/PolicyEngine/OperationWhitelist、allowlist 与超时、写入边界、审批恢复、审计证据、request/prompt safety、回滚与失败恢复证据。
- 不连接真实业务系统，不执行真实读写，不创建、更新或删除业务数据。

## 版本同步

- `pyproject.toml` 已同步到 `3.7.0`。
- FastAPI `app.version` 与 `/health.version` 已同步到 `3.7.0`。
- MCP stdio fallback client version 已同步到 `3.7.0`。
- v3.7 新增脚本 version markers 与相关测试断言已同步到 `3.7.0`。

## 边界声明

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 默认不连接真实外部 MCP、真实业务系统、真实 PostgreSQL、真实 Redis 或真实 IdP。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码或业务系统 URL 原文。
- 不绕过 ToolGateway、PolicyEngine、审批链路或审计链路。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM、真实 MCP、PostgreSQL、Redis、业务系统集成或多实例限流生产验收完成。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。

## 验证

- `python -m pytest tests/test_external_provider_acceptance_inventory_v371.py tests/test_external_mcp_acceptance_gate_v372.py tests/test_real_llm_provider_acceptance_gate_v373.py tests/test_store_redis_readiness_drill_v374.py tests/test_business_system_integration_safety_checklist_v375.py -q`
- `python -m pytest tests/test_runtime_hardening_v055.py tests/test_mcp_stdio_client_v31.py tests/test_operations_summary_v312.py -q`
- `python -m pytest tests/test_storage_v20.py tests/test_config_v20.py tests/test_deployment_guard_v60.py tests/test_request_guards_v72.py -q`
- `python -m pytest tests/test_security_v04.py tests/test_audit_v045.py tests/test_approval_resume_v042.py tests/test_v043_full_resume.py -q`
- `python -m pytest -q`：880 passed, 4 skipped, 2 warnings。
- `docker compose config`：通过，仅 Docker config 读权限 warning。
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`：通过，仅 Docker config 读权限 warning。
- `git diff --check`：通过，仅 CRLF 转换提示。

最终 tag 与 GitHub Release 创建需要用户单独确认。

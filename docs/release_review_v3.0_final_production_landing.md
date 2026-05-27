# v3.0.0 Release Review：Final Production Landing

## 1. Scope

本次 review 聚焦 v3.0.0 release prep：

- 版本号同步到 3.0.0
- Phase 10.1~10.4 文档化收口
- 发布说明与评审材料补齐
- 回归验证与边界检查归档

不包含 tag/GitHub Release 操作，不包含真实外网 LLM 执行。

## 2. Changed docs/modules

### 2.1 版本号同步

- `pyproject.toml`
- `app/main.py`（FastAPI `version` + `/health.version`）
- `app/tools/mcp/stdio_client.py`（fallback client version）
- `tests/test_runtime_hardening_v055.py`
- `tests/test_mcp_stdio_client_v31.py`

### 2.2 新增发布文档

- `RELEASE_NOTES_v3.0.0.md`
- `docs/release_review_v3.0_final_production_landing.md`

### 2.3 文档口径收口

- `README.md`
- `AGENTS.md`
- `docs/v3_final_production_landing_plan.md`
- `docs/deployment_runbook.md`
- `docs/production_readiness_checklist.md`

## 3. Verification matrix

- 安全门禁：`tests/test_deployment_guard_v60.py`
- HTTP 安全基线：`tests/test_security_headers_v71.py` + `tests/test_request_guards_v72.py`
- 日志脱敏：`tests/test_structured_logging_v73.py`
- 审计导出：`tests/test_audit_retention_export_v74.py`
- OIDC 配置预检：`tests/test_oidc_config_v75.py`
- Pilot reports 只读与脱敏：`tests/test_llm_pilot_reports_v94.py`
- 运行时版本与健康：`tests/test_runtime_hardening_v055.py` + `tests/test_mcp_stdio_client_v31.py`
- 全量回归：`python -m pytest -q`
- compose 校验：default config + prod override 缺变量失败 + 临时变量通过
- 前端验证：`npm run lint` + `npm run build`

## 4. Security/privacy boundary

- 不提交任何真实密钥（JWT_SECRET/DATABASE_URL/REDIS_URL/API key/client_secret）。
- 不记录 prompt 原文与密钥原文。
- 审计导出保持白名单字段 + redaction。
- pilot report 保持脱敏，`/llm/pilot/reports` 只读 API 保持 path traversal 防护与二次脱敏。

## 5. Operational boundary

- 默认 fake/offline，不执行真实外网 LLM。
- 默认 pytest/CI 不调用真实 LLM。
- 运维演练以 runbook + 可验证命令为主，不引入复杂平台（Prometheus/Grafana/ELK）。
- v2.9.0 tag/GitHub Release 已发布，main 超前用于 v3.0.0 release prep，不移动 v2.9.0 tag。

## 6. Known limitations

- 不等于公网生产可直接上线。
- 不等于完整生产级 SSO/OIDC 完成。
- 不等于多租户完成。
- 不等于复杂 BI 完成。
- 不等于真实 LLM 生产验收完成。

## 7. Go/No-Go

- **Go**：企业内网试点 / 准生产演示。
- **No-Go**：公网生产直接上线。
- **No-Go**：对外宣称“生产级 SSO/OIDC、多租户、复杂 BI、真实 LLM 生产验收完成”。

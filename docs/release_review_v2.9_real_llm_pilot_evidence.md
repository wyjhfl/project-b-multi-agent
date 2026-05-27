# v2.9.0 Release Review：Real LLM Controlled Pilot Evidence

## 1. 评审范围

本次 review 聚焦 v2.9.0 的 release prep：

- 版本号同步
- Phase 9.1~9.4 交付收口
- 文档口径统一
- 验证结果归档

不包含真实外网 LLM 默认启用，不包含 tag/GitHub Release 操作。

## 2. 交付完成度

### 2.1 Phase 9.1 ~ 9.4

- Phase 9.1：pilot report schema + writer（JSON/Markdown）
- Phase 9.1 P0：证据字段保真修复
- Phase 9.2：opt-in smoke 自动生成脱敏报告
- Phase 9.3：NL2SQL/Judge/audit/metrics 证据串联
- Phase 9.3 P0：Judge `llm_judge_acceptance` 审计回链
- Phase 9.4：pilot evidence review 只读 API + 前端只读入口
- Phase 9.4 P0：mojibake cleanup

### 2.2 关键能力

- 试点报告支持机器读取与人工审阅。
- evidence_links / observability 支持按 request_id 可追溯。
- `/llm/pilot/reports` 支持列表、详情读取与 markdown 预览。
- 路径穿越防护 + 读取后二次脱敏。

## 3. 默认路径与运行边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 真实 LLM smoke 仍为 opt-in。
- 本轮未执行真实外网 LLM。
- 不依赖真实外部 MCP 作为默认路径。

## 4. 安全与合规检查

- 报告脱敏边界保持：不输出 prompt 原文与密钥原文。
- 审计导出边界保持：白名单字段 + detail 脱敏。
- Judge 证据链路已具备真实可追溯语义。

## 5. 验证摘要

- `python -m pytest tests/test_llm_pilot_reports_v94.py -q`：通过
- `python -m pytest tests/test_real_llm_judge_smoke_v54.py tests/test_real_llm_smoke_v52.py -q`：通过（含 skip）
- `python -m pytest tests/test_real_llm_pilot_report_v91.py tests/test_llm_acceptance_v53.py -q`：通过
- `python -m pytest tests/test_runtime_hardening_v055.py tests/test_mcp_stdio_client_v31.py -q`：通过
- `python -m pytest -q`：`750 passed, 4 skipped`
- `docker compose config`：通过
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`：缺变量失败（预期）；注入临时变量后通过
- 前端 `npm run lint` / `npm run build`：通过

## 6. 风险与未完成项

- v2.9.0 不等于真实 LLM 生产验收完成。
- v2.9.0 不等于公网生产可直接上线。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI、真实外部 MCP 生产验收完成。

## 7. 结论

结论：**Go（可进入 v2.9.0 tag 决策）**。

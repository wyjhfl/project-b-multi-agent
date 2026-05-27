# RELEASE_NOTES_v2.9.0

## 版本定位

v2.9.0 交付 **Real LLM Controlled Pilot Evidence（受控试点证据）**，目标是完成真实 LLM 可选试点的证据闭环能力建设，默认路径仍保持 fake/offline。

## Phase 9.1 ~ 9.4 交付摘要

### Phase 9.1：pilot report schema + report writer

- 新增统一报告模型与写入器（JSON + Markdown）。
- 报告默认目录：`docs/reports/real_llm_pilot/`。
- 报告默认脱敏：不记录 prompt 原文，不输出密钥原文。

### Phase 9.1 P0：证据字段保真修复

- 修复过宽脱敏导致的证据字段误伤。
- 确保证据字段保真：tokens/cost/cache_hit/budget_action/request_id 等可用于复盘。

### Phase 9.2：opt-in smoke 自动生成脱敏报告

- 在 NL2SQL 与 LLMJudge 的 opt-in smoke 流程中接入自动报告生成。
- 支持 `REAL_LLM_PILOT_REPORT_DIR` 覆盖输出目录。
- 未显式 opt-in 时默认 skip，不影响默认测试与 CI。

### Phase 9.3：NL2SQL / Judge / audit / metrics 证据串联

- 串联 acceptance summary、审计事件、日志 request_id、runtime metrics 摘要。
- 报告新增 evidence_links / observability 脱敏摘要，支持可追溯复盘。

### Phase 9.3 P0：Judge 审计回链收口

- Judge 证据链路写入并回链可追溯 `llm_judge_acceptance` 审计事件。
- 不再是字段占位，具备真实可追溯语义。

### Phase 9.4：pilot evidence review 只读能力

- 后端新增只读 API：
  - `GET /llm/pilot/reports`
  - `GET /llm/pilot/reports/{report_id}`
  - `GET /llm/pilot/reports/{report_id}/markdown`
- 前端 `/llm` 页面新增 Pilot Evidence 只读区域。
- 只读入口不触发真实 LLM，不支持上传/编辑。

### Phase 9.4 P0：mojibake cleanup

- 完成 pilot evidence review API 与测试文本乱码清理。
- 保持中文错误信息与文档口径可读。

## 安全与边界

- `/llm/pilot/reports` 具备 path traversal 防护。
- 读取报告后执行二次脱敏，降低历史数据泄漏风险。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- 本轮未执行真实外网 LLM。
- 不依赖真实外部 MCP 作为默认路径。

## 验证摘要（release prep）

- 后端全量：`750 passed, 4 skipped`
- 前端：`npm run lint` / `npm run build` 通过
- `docker compose config` 通过
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`：
  - 缺变量按预期失败
  - 注入临时 `JWT_SECRET` / `DATABASE_URL` / `REDIS_URL` 后通过

## 与 v2.8.0 的关系

- v2.8.0 tag 与 GitHub Release 已发布。
- main 超前 v2.8.0 tag 属于 v2.9.0 后续演进。
- 本次仅做 v2.9.0 release prep，不改动 v2.8.0 tag。

## 声明

- v2.9.0 不等于真实 LLM 生产验收完成。
- v2.9.0 不等于公网生产可直接上线。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI、真实外部 MCP 生产验收完成。

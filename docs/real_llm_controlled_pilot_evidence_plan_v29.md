# v2.9 Real LLM Controlled Pilot Evidence 规划

## 1. 目标定位

- v2.9 目标：**Real LLM Controlled Pilot Evidence**。
- 只做 opt-in 真实 LLM 试点证据闭环，不默认启用真实 LLM。
- 默认 fake/offline 路径不变，默认 pytest/CI 不调用真实 LLM。
- 本阶段不等于真实 LLM 生产验收完成，不等于公网生产可直接上线。

## 2. 证据闭环范围

### 2.1 试点执行证据

- 记录真实 smoke 执行证据（仅在显式开关开启后执行）。
- 证据字段应包含：
  - provider / model / base_url（脱敏摘要）
  - request_id
  - latency_ms
  - prompt_tokens / completion_tokens / total_tokens
  - cost
  - fallback_reason
  - budget_action
  - cache_hit

### 2.2 业务链路覆盖

- NL2SQL preview / run 的真实 LLM 试点证据。
- LLMJudge 试点证据。
- 审计导出（JSONL）证据。
- structured log 证据。
- runtime metrics 证据。

### 2.3 失败证据同样归档

失败路径必须归档，至少覆盖：

- network_error
- auth_error
- rate_limit
- budget_block
- fallback

## 3. 报告产物与目录建议

建议新增报告目录：

- `docs/reports/real_llm_pilot/`

建议按批次归档，例如：

- `docs/reports/real_llm_pilot/2026-xx-xx_pilot_batch_01.md`
- `docs/reports/real_llm_pilot/2026-xx-xx_pilot_batch_01.json`

## 4. 脱敏与合规边界

- 报告必须脱敏，不包含以下原文：
  - prompt 原文
  - API key / token / secret
  - Authorization / Cookie
  - 数据库密码与连接串密码
- 对外展示仅允许脱敏摘要与统计字段。
- 任何失败日志同样适用脱敏边界。

## 5. 阶段拆分（建议）

### Phase 9.1：pilot report schema + report writer（已完成）

- 已定义统一证据 schema（`PilotReportSummary` / `PilotReportCase` / `PilotReportArtifact`）。
- 已提供报告写入器（结构化 JSON + Markdown 摘要），默认输出目录 `docs/reports/real_llm_pilot/`。
- 报告默认脱敏：不包含 prompt 原文与密钥原文。
- 已完成 Phase 9.1 P0 cleanup：修复“证据字段保真 + 敏感字段脱敏”，避免 token/cost/api_key_present 等证据字段被误脱敏。
- 默认不执行真实 LLM；Phase 9.2 再接入 opt-in smoke 自动生成报告。

### Phase 9.2：opt-in smoke 自动生成脱敏报告（已完成）

- 已在 opt-in smoke（NL2SQL/Judge）流程中自动生成脱敏报告（JSON + Markdown）。
- 默认输出目录 `docs/reports/real_llm_pilot/`，可通过 `REAL_LLM_PILOT_REPORT_DIR` 覆盖。
- 保持默认关闭，不影响默认测试与 CI，不会默认触发真实外网 LLM。

### Phase 9.3：NL2SQL / Judge / audit / metrics 证据串联（已完成）

- 已串联 NL2SQL、LLMJudge、审计与指标，形成单次试点完整证据链。
- 报告新增 evidence_links / observability（脱敏摘要），支持按 request_id 关联检索。
- runtime metrics 仅记录安全摘要字段，不包含 prompt 与密钥原文。
- 已完成 Phase 9.3 P0 cleanup：Judge evidence_links 不再是占位字段，写入可追溯 `llm_judge_acceptance` 审计事件。

### Phase 9.4：pilot evidence review API 或前端只读入口

- 提供只读证据审查入口（API 或前端）。
- 不提供敏感字段明文展示与导出。

### Phase 9.5：v2.9 release prep

- 汇总证据覆盖度、失败分布与边界符合性。
- 完成 v2.9 文档收口与发布准备。

## 6. 验收准入条件（建议）

- 至少完成 1 轮可复现的 opt-in 真实 LLM 试点报告。
- 至少包含成功与失败样本各一类。
- 报告字段完整、脱敏通过、可追溯到 request_id。
- 默认路径（fake/offline + 默认 CI）不受影响。

## 7. 边界声明

- v2.9 仅为受控试点证据能力增强，不宣称真实 LLM 生产验收完成。
- 不宣称公网生产可直接上线。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 已完成。
- 不宣称真实外部 MCP 生产验收完成。

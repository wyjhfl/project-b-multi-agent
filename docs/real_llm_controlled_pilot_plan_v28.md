# v2.8 Controlled Real LLM Pilot 规划

## 1. 背景基线

- v2.5 已具备真实 LLM 的 opt-in 验收能力：provider preflight、real_llm smoke、LLMJudge smoke、预算与缓存闭环。
- v2.7 已完成安全基线：CORS、安全响应头、请求防护、结构化日志脱敏、审计留存与导出边界、OIDC 最小接入骨架。
- 默认路径仍为 fake/offline，默认 pytest/CI 不调用真实 LLM。

## 2. v2.8 目标定位

- 目标：**Controlled Pilot（受控试点）**。
- 不默认启用真实 LLM，不进入默认 CI，不作为生产验收完成声明。
- 所有真实调用必须满足显式开关、配置完整、预算边界、审计记录、人工报告。

## 3. 能力范围

### 3.1 Provider Readiness / Preflight

- `/llm/preflight` 返回统一结构：
  - `provider` / `model` / `base_url`（脱敏）
  - `api_key_env` / `api_key_present`
  - `network_check_allowed` / `network_check_requested` / `network_check_executed`
  - `errors` / `warnings`
- 默认不联网；`network_check=true` 只有在显式开关和完整配置满足时才允许。

### 3.2 Acceptance Summary 统一口径

- 统一字段：
  - `provider` / `model`
  - `real_call_attempted` / `real_call_succeeded`
  - `fallback_used` / `fallback_reason`
  - `prompt_tokens` / `completion_tokens` / `total_tokens`
  - `cost` / `latency_ms`
  - `cache_hit` / `budget_action`
  - `request_id` / `error_type` / `warnings`
- 禁止记录 prompt 原文与密钥原文。

### 3.3 Budget / Cache / Fallback

- `budget disabled` 不阻断。
- `hard limit + fallback_to_mock=true`：走 fallback，返回可观测原因。
- `hard limit + fallback_to_mock=false`：返回明确错误，不抛 500。
- 相同请求二次命中缓存时，`cache_hit=true` 且 `real_call_attempted=false`。

### 3.4 LLMJudge Pilot

- FakeJudge 默认保持不变。
- real provider 仍为 opt-in。
- `fallback_to_fake=true` 时可降级。
- `fallback_to_fake=false` 返回 `llm_unavailable`，不抛 500。

### 3.5 审计 / 日志 / 指标联动

- 记录真实 LLM 尝试、成功、fallback、budget block。
- 审计 detail 必须脱敏；JSONL 导出不得泄漏 prompt/key。
- Runtime 指标可观测 `llm_budget` / `llm_cache` / `cost` 摘要。

## 4. 前端试点页

- 新增 LLM Pilot 页面展示：
  - preflight 状态
  - provider/model/base_url 配置状态
  - api_key_env 与 present/missing
  - network_check 是否允许
  - errors/warnings
- 不提供 API key 输入，不展示密钥原文。

## 5. 验收报告模板

- real_llm smoke 报告模板补充：
  - `request_id`
  - `fallback_reason`
  - `budget_action`
  - `cache_hit`
  - `cost`

## 6. 边界声明

- 本阶段是受控试点，不等于真实 LLM 生产验收完成。
- 不宣称公网生产可直接上线。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 已完成。
- 不宣称真实外部 MCP 生产验收完成。

## 10. v2.8 Controlled Real LLM Pilot（执行中）

- 当前阶段：受控试点（Controlled Pilot），不作为真实 LLM 生产验收完成声明。
- 默认路径不变：fake/offline，默认 pytest/CI 不调用真实 LLM。
- 新增 `/llm/preflight` 结构化返回与前端 LLM Pilot 状态页，用于配置预检和风险可视化。
- acceptance summary 已统一口径：provider/model、real_call_attempted、real_call_succeeded、fallback_reason、tokens/cost、budget_action、cache_hit、request_id、error_type、warnings。
- 审计/日志/导出边界保持：不记录 prompt 原文，不输出 API key/token/password/secret/数据库密码原文。
- 真实 LLM 试点仍需外部环境、密钥注入、预算控制与人工 smoke 报告。

# RELEASE_NOTES_v2.8.0

## Highlights

v2.8.0 交付 **Controlled Real LLM Pilot（受控试点）** 阶段能力，重点是“可观测、可回退、可审计”的真实 LLM 试点收口，而非默认放开真实外网调用。

- `/llm/preflight` 状态观测收敛与默认关闭语义修正
- 前端 `/llm` 试点状态页
- acceptance_summary 字段统一
- budget/cache/fallback/LLMJudge opt-in 行为收敛
- 审计 / 日志 / 指标联动强化（保持脱敏边界）

## 关键能力

### 1) Provider Readiness / Preflight

- `/llm/preflight` 返回统一结构：
  - `provider` / `model` / `base_url`（脱敏）
  - `api_key_env` / `api_key_present`
  - `network_check_allowed` / `network_check_requested` / `network_check_executed`
  - `checks` / `warnings` / `errors`
- 默认不开启真实联网检查。
- 当 `real_llm_acceptance_enabled=false` 或 `real_llm_preflight_enabled=false` 时：
  - `status=disabled`
  - `allowed=false`
  - `network_check_executed=false`
  - 不因 model/key 缺失进入 errors。

### 2) acceptance_summary 统一口径

- 统一字段覆盖：
  - `provider` / `model`
  - `real_call_attempted` / `real_call_succeeded`
  - `fallback_used` / `fallback_reason`
  - `prompt_tokens` / `completion_tokens` / `total_tokens`
  - `cost` / `latency_ms`
  - `cache_hit` / `budget_action`
  - `request_id` / `error_type` / `warnings`
- 明确不记录 prompt 原文与密钥原文。

### 3) Budget / Cache / Fallback

- budget disabled 不阻断默认路径。
- hard limit + fallback_to_mock=true：触发可观测 fallback。
- hard limit + fallback_to_mock=false：返回明确错误，不抛 500。
- 相同请求二次命中缓存时可观测 `cache_hit=true`。

### 4) LLMJudge opt-in 收敛

- FakeJudge 默认不变。
- real provider 仍为 opt-in。
- `fallback_to_fake=true` 可降级。
- `fallback_to_fake=false` 返回 `llm_unavailable`，不抛 500。

### 5) 审计 / 日志 / 指标联动

- 记录真实 LLM 尝试、成功、fallback、budget block。
- 审计与导出保持字段白名单 + 脱敏边界。
- 继续禁止导出 prompt 原文与密钥原文。

## 默认路径与边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 真实 LLM smoke 仍为 opt-in，不进入默认 CI。
- 默认不接真实外部 MCP。
- 不提交 API key/token/client_secret/账号凭据。

## 验证摘要（release prep）

- 后端全量测试：`730 passed, 4 skipped`。
- 前端：`npm run lint`、`npm run build` 通过。
- `docker compose config` 通过。
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`：
  - 缺变量时按预期失败。
  - 注入临时安全变量后通过。

## 与 v2.7.0 的关系

- `v2.7.0` tag 与 GitHub Release 已发布。
- `v2.7.0` tag 固定在 `2076111cb786df76a941ebf28f550f68f4131147`。
- 当前 main 超前 tag，v2.8.0 为后续版本准备。

## Known boundaries

- v2.8.0 是 Controlled Real LLM Pilot，不等于真实 LLM 生产验收完成。
- 不等于公网生产可直接上线。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 已完成。
- 不宣称真实外部 MCP 生产验收已完成。

# v2.3.0 Phase 4 规划与进展（LLM Provider + Guardrails）

## 0. 范围与边界

- 本文档用于记录 Phase 4 的分阶段规划与当前状态。
- 不涉及版本号变更、tag、Release 操作。
- 默认运行模式必须保持 fake/offline。
- 默认测试不调用真实 LLM、不访问外网、不依赖 API key。

## 1. 当前状态总览（截至 Phase 4.3 Review Cleanup）

### 1.1 Phase 4.1（已完成）

- `LiteLLMProvider` 已具备：
  - 配置校验与明确错误类型映射。
  - 超时、重试、退避等基础稳定性控制。
  - `generate_with_metadata` 结构化元数据输出（token/cost/request_id/latency）。
- 默认仍使用 `FakeLLMProvider`，保证离线可跑。

### 1.2 Phase 4.2（已完成）

- `LLMNL2SQLGenerator` 已完成结构化 JSON 校验与 fallback 收口。
- SQL 执行前始终经过 `SQLGuard`。
- `fallback_to_mock=true/false` 语义已收口并由测试覆盖。
- `NL2SQLPipeline` 已可记录 provider token/cost 元数据。

### 1.3 Phase 4.3（已完成）

- `LLMJudgeProvider` 已从 unavailable skeleton 升级为可选实接实现：
  - 输入包含 `query/expected/actual/rubric`。
  - 期望输出 JSON：`score/passed/reasoning/confidence`。
  - 解析失败、provider 不可用时支持 fallback 或 `llm_unavailable` 返回。
- 默认仍使用 `FakeJudge`，不会破坏离线路径。
- `BadCaseRunner` 已接入 judge token/cost 元数据记录。
- API 可按请求覆盖 `judge_provider` 与 `judge_fallback_to_fake`。

## 2. Judge 配置口径（Phase 4.3 已对齐）

### 2.1 配置项

- `judge_provider`（默认 `fake`）
- `judge_fallback_to_fake`（默认 `true`）
- `judge_model`（默认空）
- `judge_timeout_seconds`（默认 `15.0`）
- `judge_max_retries`（默认 `0`）
- `judge_retry_backoff_seconds`（默认 `0.5`）

### 2.2 实际生效规则

- `LLMJudgeProvider` 在创建 `LiteLLMProvider` 时使用 `judge_*` 配置覆盖：
  - `model -> judge_model`
  - `timeout_seconds -> judge_timeout_seconds`
  - `max_retries -> judge_max_retries`
  - `retry_backoff_seconds -> judge_retry_backoff_seconds`
- `temperature` 当前沿用 `llm_temperature`（最小改动策略）。
- NL2SQL 路径继续使用 `llm_*` 配置，不受 `judge_*` 影响。

## 3. API 行为（bad case eval）

- 默认：
  - `use_judge=false`：不启用 Judge。
  - `use_judge=true` 且未传覆盖参数：使用 settings 中的 judge 配置。
- 请求可覆盖：
  - `judge_provider`（如 `fake` / `litellm`）
  - `judge_fallback_to_fake`（本次运行覆盖）
- 不可用 provider、配置缺失、JSON 解析失败不会导致 API 500。

## 4. Phase 4.4（已完成最小闭环）

- 已新增 `GuardrailsEngine` 统一编排层，提供：
  - `check_input`
  - `check_llm_output`
  - `check_sql`
  - `sanitize_response`
- 已新增 `PIIGuard` 规则检测与脱敏：
  - 邮箱、手机号、身份证、银行卡、token/key 形态。
- 已在 NL2SQL 与 API 入口最小接入：
  - `/nl2sql/preview`
  - `/nl2sql/execute`（对应 run 链路）
  - `/tasks`
- 保持既有硬约束：
  - PromptInjectionGuard 高风险仍 block。
  - SQLGuard 仍是 SQL 执行前硬门禁。

### 4.1 PII 检测边界说明

- 当前是规则型检测，不是完整 DLP 系统。
- 主要用于减少明显敏感信息泄露风险，不保证覆盖所有变体。
- 检测结果用于 warning/redact 与审计辅助，不替代合规审查流程。

### 4.2 Guardrails 定位说明

- Guardrails 是规则编排层，不是黑箱安全模型。
- 不绕过现有 PolicyEngine / SQLGuard / PromptInjectionGuard。
- 默认 fake/offline 路径保持可跑，默认测试不调用真实 LLM。

## 5. Phase 4.5 规划（未开始）

> 本阶段仅保留规划，不在本次改动中实现。

- token/cost 预算控制（task/session/day）。
- 超时、重试、降级统一策略。
- 缓存策略（query + schema_hash + prompt_version）。
- 成本与稳定性可观测汇总。

## 6. 测试与验收口径

- 默认 `python -m pytest -q` 必须离线可跑，不调用真实 LLM。
- 真实 provider 测试应通过 mock 或可选集成测试标记隔离。
- API 路径必须保证错误可控返回，不抛 500。

## 7. 非目标（当前仍不做）

- 默认测试接入真实外部 LLM。
- 提交任何 API key 或敏感凭据。
- 宣称系统已可直接生产上线。
- 在 Phase 4.3 提前实现 Phase 4.4/4.5 的完整能力。

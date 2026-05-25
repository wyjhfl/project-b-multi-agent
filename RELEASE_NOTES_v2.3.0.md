# Project B v2.3.0 - LLM Provider + Guardrails Runtime

## 1. Highlights

- 完成 Phase 4 全阶段收口：LLM Provider 硬化、NL2SQL 真实 LLM 生成链路、可选 LLM-as-Judge、Guardrails + PII、防护、预算/缓存/降级闭环。
- 默认行为保持离线可跑：`fake/offline` 仍为默认路径，默认测试不调用真实 LLM。
- 与 v2.2.0 相比，重点新增 LLM 调用治理与安全防护编排能力。

## 2. LiteLLMProvider hardening

- 增强配置校验与错误类型映射（配置错误、认证错误、限流、超时、模型错误、响应错误）。
- 增加 `generate_with_metadata` 结构化元数据输出：`provider/model/tokens/cost/request_id/latency/error_type`。
- 支持超时、重试、退避参数，且默认配置保守。

## 3. NL2SQL structured validation + fallback

- `LLMNL2SQLGenerator` 增加结构化 JSON 校验：`sql/confidence/reasoning/selected_tables`。
- 区分 fallback 原因：非 JSON、结构非法、provider 异常、SQLGuard 拦截等。
- `fallback_to_mock=true` 时可降级到 mock；`fallback_to_mock=false` 时按失败返回，不执行 SQL。
- SQL 执行前仍强制经过 `SQLGuard`。

## 4. Optional LLM-as-Judge

- `LLMJudgeProvider` 支持可选真实 provider 路径，输入 `query/expected/actual/rubric`，输出 `score/passed/reasoning/confidence`。
- 支持 `judge_fallback_to_fake` 策略：provider 不可用或响应非法时回退 FakeJudge 或返回 `llm_unavailable`。
- `BadCaseRunner` 接入 judge 元数据记录（token/cost 等）。

## 5. Guardrails + PII protection

- 新增 `GuardrailsEngine` 统一编排输入/输出/SQL 检查与响应脱敏。
- 新增规则型 PII 检测与脱敏（邮箱、手机号、身份证、银行卡、token/key 形态）。
- 修复 PII 泄漏风险：对外 findings 仅暴露 `masked_value`，不暴露原始敏感值。
- API 入口（`/nl2sql/preview`、`/nl2sql/execute`、`/tasks`）接入最小防护链路。

## 6. Budget/cache/fallback loop

- 新增 LLM 预算控制（默认关闭）：支持调用前预算判断与调用后 usage 记录。
- 新增进程内内存缓存（默认关闭）：支持 NL2SQL/Judge 结果缓存与 TTL。
- 预算阻断时按策略回退（mock 或 fake judge）或失败返回，避免盲目继续执行。
- Metrics 增加预算/缓存状态的运行期可观测字段。

## 7. Verification

- 全量测试基线：**636 passed**。
- 关键回归：
  - `python -m pytest tests/test_runtime_hardening_v055.py -q`
  - `python -m pytest tests/test_llm_budget_cache_v45.py tests/test_guardrails_pii_leak_v44.py tests/test_llm_judge_v43.py -q`
  - `python -m pytest -q`
- Docker 验证：
  - `docker compose config` 通过
  - `docker compose build app` 通过

## 8. Boundaries

- 不宣称默认启用真实 LLM。
- 不宣称生产可直接上线。
- 不宣称完整 DLP（当前为规则型 PII 检测与脱敏）。
- 不宣称完整成本账单系统（当前为运行期轻量预算与聚合观测）。
- 不宣称真实外部 MCP Server 生产验收已完成（当前 real 协议路径基于 fake fixture 验收）。
- 不宣称完整 LangGraph native Command resume。

## 9. Upgrade notes

- 版本升级到 `v2.3.0`。
- 默认行为不变：仍为 fake/offline，可离线运行全量测试。
- 如需启用真实 provider，请显式配置 provider/model/key/timeout/retry，并在独立环境完成验收。

## 10. Next phase

- Phase 5 建议聚焦：真实外部环境验收与治理闭环（真实 LLM/真实 MCP 的稳定性、成本、合规、回放与运维策略）。

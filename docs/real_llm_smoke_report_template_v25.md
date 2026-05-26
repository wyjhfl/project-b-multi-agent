# v2.5 真实 LLM Smoke 验收报告模板（Opt-in）

> 说明：本模板用于 **opt-in smoke** 记录，不代表真实 LLM 生产验收完成。

## 1. 基本信息

- 执行时间：
- 执行人：
- 执行环境（本地/CI job 名称）：
- 代码版本（commit hash）：

## 2. 配置摘要（脱敏）

- provider：
- model：
- base_url（脱敏）：
- api_key_env_name：
- 是否启用 opt-in 开关：
  - REAL_LLM_SMOKE_ENABLED=
  - REAL_LLM_ACCEPTANCE_ENABLED=
  - REAL_LLM_PREFLIGHT_ENABLED=
  - REAL_LLM_PREFLIGHT_NETWORK_CHECK=

## 3. Preflight 结果

- 接口：`GET /llm/preflight?network_check=true`
- status：
- allowed：
- checks 摘要：
- warnings：
- errors：
- latency_ms：

## 4. Provider 基础调用结果

- 调用方式：LiteLLMProvider / create_provider
- prompt：`请只回复 ok`
- 是否成功：
- request_id：
- latency_ms：
- prompt_tokens：
- completion_tokens：
- total_tokens：
- cost：
- error_type（如失败）：

## 5. NL2SQL Preview 结果

- 请求：`/nl2sql/preview`（`generator=llm`、`provider=litellm`、`fallback_to_mock=true`）
- query：
- HTTP 状态码：
- guard_allowed：
- generator_used：
- provider_used：
- fallback_used：
- fallback_reason：
- warnings：

## 6. 错误与归因

- 是否出现错误：
- 错误类型（auth/timeout/rate_limit/model/response/other）：
- 初步归因（配置/网络/模型/响应结构）：
- 修复建议：

## 7. 结论

- 本次 smoke 结论：通过 / 未通过 / 部分通过
- 是否建议进入下一阶段（Phase 5.3）：
- 备注：

---

**边界声明**：  
该报告仅表示在当前环境下完成了 opt-in smoke 验证，**不等于真实 LLM 生产验收完成**。

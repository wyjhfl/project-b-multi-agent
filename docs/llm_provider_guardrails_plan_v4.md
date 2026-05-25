# v2.3.0 Phase 4 Planning：LLM Provider + Guardrails 生产化规划

## 0. 范围与边界

- 本文档仅做 Phase 4 规划，不实现代码。
- 不改版本号，不创建 tag。
- 默认配置必须保持 fake/offline，可在无外部 API key 情况下跑完整测试。
- 不在默认测试中调用真实 LLM，不提交任何 API key，不宣称可直接生产上线。

## 1. 当前状态审查（真实差距）

> 说明：仓库中不存在 `app/llm`、`app/eval`、`app/nl2sql` 顶层目录；当前对应能力主要在：
> - `app/agent/nl2sql/*`
> - `app/harness/eval/*`
> - `app/services/nl2sql_pipeline.py`
> - `app/harness/security/*`、`app/harness/policy/*`

### 1.1 FakeJudge / LLMJudgeProvider

- `app/harness/eval/judge.py`
  - `FakeJudge`：规则打分，已可用于离线评测。
  - `LLMJudgeProvider`：当前固定返回 `llm_unavailable`，未调用真实 provider。
- 差距：
  - 无真实评分 prompt、无评分结果结构约束、无一致性校验。
  - 无 token/cost 计量接入 Judge 调用路径。

### 1.2 NL2SQL（mock + llm fallback）

- `app/services/nl2sql_pipeline.py`
  - 支持 `generator=mock|llm`，默认 mock。
  - llm 路径可触发 `create_provider()`；配置缺失时可 fallback 到 mock。
- `app/agent/nl2sql/provider.py`
  - `FakeLLMProvider`：内置规则返回 JSON。
  - `LiteLLMProvider`：有基础调用壳，但配置、超时、重试、错误分型、成本计量能力不完整。
- `app/agent/nl2sql/llm_generator.py`
  - 已有 prompt 渲染、JSON 解析、`SQLGuard` 校验、fallback。
- 差距：
  - 真实 provider 的稳定性控制（timeout/retry/backoff）不足。
  - 结构化输出约束较弱（依赖 JSON 解析，缺强校验）。
  - 成本/令牌统计当前主要是占位 0 值。

### 1.3 安全与策略

- `app/harness/security/injection_guard.py`：规则型 prompt injection 检测（block/warn）。
- `app/agent/nl2sql/sql_guard.py`：SQL 只读白名单、关键字拦截、自动 LIMIT。
- `app/harness/policy/operation_whitelist.py` + `engine.py`：工具白名单与风险分级。
- 差距：
  - 缺统一 Guardrails 编排层（输入→生成→输出→执行）。
  - 缺 PII 检测与脱敏策略。
  - 缺 LLM 输出合规检查（例如敏感指令回显、危险操作建议）。

## 2. Phase 4.1：LiteLLMProvider 接入计划

目标：在不破坏默认 fake/offline 的前提下，提供可选真实 provider 运行能力。

### 2.1 设计要点

- Provider 抽象保持 `LLMProvider` 接口不变，扩展调用参数（timeout、max_retries、temperature 等）。
- `LiteLLMProvider` 增加：
  - 明确错误类型：配置错误、鉴权错误、超时错误、限流错误、模型错误。
  - 可配置 timeout/retry/backoff（默认保守）。
  - 响应元数据回传：model、usage、request_id（若可得）。
- 保持 `llm_provider=fake` 默认，`litellm` 仅显式启用。

### 2.2 配置建议（新增/细化）

- `LLM_PROVIDER=fake|litellm`（默认 fake）
- `LLM_MODEL`（默认空）
- `LLM_API_KEY`（默认空）
- 建议新增：
  - `LLM_TIMEOUT_SECONDS`（默认 10~20）
  - `LLM_MAX_RETRIES`（默认 0 或 1）
  - `LLM_RETRY_BACKOFF_SECONDS`
  - `LLM_BUDGET_USD_SOFT/HARD`

### 2.3 验收标准

- 无 key 时：llm 路径可明确降级到 mock，不抛 500。
- 有 key 且显式开启时：可完成基础调用，错误可观测。
- 默认测试全通过且不依赖外网。

## 3. Phase 4.2：NL2SQL 真实 LLM 生成计划

目标：让 `LLMNL2SQLGenerator` 在真实 provider 下可控、可回退、可审计。

### 3.1 方案

- 强化 prompt 模板版本化：`prompt_version` 入结果。
- 强化输出结构校验：`sql/confidence/reasoning/selected_tables` 必填校验。
- 失败分层：
  - 解析失败 / 空 SQL / 非法 SQL / provider 异常。
- 与 `SQLGuard` 串联保持硬约束：即使 LLM 成功，也必须 guard 通过才可执行。

### 3.2 回退策略

- `fallback_to_mock=true` 时：
  - provider 或解析失败自动退回 `MockNL2SQLGenerator`。
  - 返回 `fallback_used=true` 和 `fallback_reason`。
- `fallback_to_mock=false` 时：
  - 返回失败且含明确 error_type，不执行 SQL。

### 3.3 验收标准

- 真实 LLM 生成可产出有效 SQL。
- 危险 SQL 仍被 `SQLGuard` 稳定拦截。
- 降级路径可复现且可观测。

## 4. Phase 4.3：LLM-as-Judge 真实评测计划

目标：在保留 FakeJudge 的同时，提供可选真实 Judge。

### 4.1 方案

- 扩展 `LLMJudgeProvider`：
  - 评分输入模板（query、expected、actual、rubric）。
  - 结构化输出：`score`、`passed`、`reasoning`、`confidence`。
  - 失败降级：不可用时自动回 FakeJudge 或返回 `judge_unavailable`（可配置）。
- 增加评分稳定性保护：
  - score 范围校验（0~1）。
  - 多轮采样可选（默认关闭）。

### 4.2 验收标准

- 默认仍走 FakeJudge，离线可跑。
- 显式开启真实 Judge 时可跑通，并记录评分元数据。
- 评测报告可区分 fake/real judge 来源。

## 5. Phase 4.4：Guardrails 规划

目标：形成“输入防护 + SQL 防护 + 输出防护 + 危险操作防护”闭环。

### 5.1 Prompt Injection

- 复用 `PromptInjectionGuard`，增加规则版本与命中审计字段。
- 对高风险注入默认 block，中风险 warn + 审计。

### 5.2 SQL 安全

- `SQLGuard` 继续作为执行前硬闸。
- 增加二次检查位点：LLM 输出后、执行前再次校验（防中间篡改）。

### 5.3 PII 保护

- 新增 PII 检测器（规则优先，模型增强可后置）：
  - 邮箱、手机号、身份证号、银行卡等模式识别。
- 响应脱敏策略：
  - 默认脱敏显示；
  - 高权限角色可选查看原文（需 RBAC 控制，默认关闭）。

### 5.4 危险操作

- 保持 ToolGateway / PolicyEngine / HITL 主链路不绕过。
- LLM 输出中若包含“建议直接执行高风险操作”，标记 warning 并进入审批语义。

## 6. Phase 4.5：成本控制规划

目标：令牌、成本、时延可观测并可限流降级。

### 6.1 能力点

- token/cost 真实记录（替代当前占位 0 值）：
  - prompt_tokens / completion_tokens / total_cost
  - provider/model 维度统计
- 预算控制：
  - 任务级预算、会话级预算、日预算（soft/hard）。
- 超时与重试：
  - 超时立即失败或降级，不无限重试。
- 缓存：
  - query + schema_hash + prompt_version 命中缓存（只读场景优先）。
- 降级：
  - 超预算/超时/限流时自动降级 mock 或返回受控错误。

### 6.2 验收标准

- 成本汇总 API 可反映真实 token/cost。
- 超预算触发后行为可预测（降级或失败）。
- 默认离线测试不依赖真实 token/cost。

## 7. 配置设计（默认 fake/offline）

### 7.1 原则

- 默认值必须让 `python -m pytest -q` 在无外网、无 key 环境可通过。
- 真实 provider 仅在显式环境变量开启。

### 7.2 建议配置分层

- 基础：
  - `llm_provider=fake`
  - `nl2sql_generator=mock`
- 可选真实：
  - `llm_provider=litellm`
  - `llm_model=<model>`
  - `llm_api_key=<key>`
  - `llm_timeout_seconds`
  - `llm_max_retries`
- Judge：
  - `judge_provider=fake|litellm`（建议新增）
  - `judge_fallback_to_fake=true`（建议新增）

## 8. 测试计划

### 8.1 单元测试（默认必跑）

- Fake provider 路径：
  - NL2SQL mock/fake 生成稳定。
  - FakeJudge 评分稳定。
- 无 key 降级：
  - `generator=llm` + 无 key 时 fallback 行为正确。
- Guardrails：
  - prompt injection block/warn
  - SQLGuard 危险 SQL 拦截
  - PII 检测/脱敏（新增后）
- 成本控制：
  - 占位成本与真实成本路径分离测试。

### 8.2 集成测试（可选）

- 真实 provider 集成测试单独标记（如 `-m integration_llm`）：
  - 默认 CI 不跑。
  - 需显式注入密钥和开关。

### 8.3 回归保证

- 默认 `pytest -q` 不调用真实 LLM API。
- 旧 API 行为与默认模式不破坏。

## 9. 风险与边界

### 9.1 主要风险

- 真实 LLM 不稳定导致结果漂移。
- 预算与重试策略不当导致成本失控。
- Guardrails 误杀或漏拦截。
- 多 provider 行为差异导致评测不一致。

### 9.2 非目标（Phase 4 不做）

- 不在默认测试中调用真实 LLM。
- 不提交 API key 或敏感配置。
- 不宣称“生产可直接上线”。
- 不把当前规则型安全防线替换为黑箱模型判定。

## 10. 分阶段实施建议（执行顺序）

1. **Phase 4.1**：Provider 接口与配置硬化（先稳定入口）。
2. **Phase 4.2**：NL2SQL 真实生成 + fallback + 结构化校验。
3. **Phase 4.3**：LLM-as-Judge 可选接入 + FakeJudge 回退。
4. **Phase 4.4**：Guardrails 编排与 PII 防护补齐。
5. **Phase 4.5**：成本控制、预算、缓存、降级闭环。

> 推荐策略：先“默认稳定离线”，再“可选真实在线”，最后“成本与安全收口”。

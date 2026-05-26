# v2.5 真实 LLM 可选验收包规划（不进默认验收）

## 1. 背景与目标

本规划用于 v2.5 阶段的“真实 LLM 可选验收包”设计，目标是：

- 在不破坏默认离线可跑路径的前提下，提供可选、可控、可审计的真实 LLM 验证方案；
- 明确真实验收前置条件、执行流程、风险边界和结果归档方式；
- 形成“默认 fake/offline + opt-in real”双轨运行策略。

本规划只做文档设计，不启用真实 LLM 调用，不接真实外部 MCP。

## 2. 当前能力盘点（v2.3 / v2.4）

### 2.1 已有能力

- 已有 `LLMProvider` 抽象与 `LiteLLMProvider` 可选路径；
- NL2SQL 已支持结构化校验、Guardrails、fallback_to_mock；
- LLMJudge 已支持可选 provider 路径，默认 `FakeJudge`；
- 已有 token/cost/budget/cache/fallback 的运行时闭环能力；
- 前端 v2.4 运营台已可查看 Tasks / Approvals / Audit / Metrics / Tools / NL2SQL。

### 2.2 默认路径

- 默认仍为 fake/offline，不需要 API key；
- 默认测试与默认 CI 不访问真实外网 LLM；
- 默认演示不依赖真实外部 MCP。

## 3. 与真实 LLM 生产验收之间的差距

当前与“真实 LLM 生产验收”之间的主要差距：

1. 缺少标准化 provider preflight 清单与门禁；
2. 缺少稳定、可重放的 opt-in 真实 LLM smoke 流程；
3. 真实 provider 下 token/cost 与预算告警尚未形成标准验收模板；
4. LLMJudge 真实路径缺少专项验收记录与失败归因模板；
5. 缺少可交付的验收报告模板与 release 口径模板。

## 4. Phase 5.1：Provider Preflight

目标：在调用真实 LLM 前，先验证配置与环境完整性。

当前状态：**已完成最小实现**（v2.5 Phase 5.1）。

已实现能力：

- 新增 `/llm/preflight` API；
- 默认执行离线配置检查，不访问网络；
- 仅在显式满足以下条件时才允许网络检查：
  - `real_llm_acceptance_enabled=true`
  - `real_llm_preflight_enabled=true`
  - `real_llm_preflight_network_check=true`
  - `real_llm_model` 与 API key 环境变量完整；
- 配置缺失返回结构化结果，不返回 500；
- 返回与日志不暴露 API key 原文。
- 已补齐 `real_llm_base_url -> preflight -> create_provider -> LiteLLMProvider -> litellm.completion(api_base)` 传递闭环。
- `latency_ms` 统一表示 preflight 总耗时，不重复叠加 network_check 单项耗时。

建议项：

- 校验必需配置：provider、model、base_url（如需要）、api_key（环境变量）；
- 校验网络可达性（仅在手动 opt-in 环境执行）；
- 校验超时/重试参数边界（timeout、max_retries、backoff）；
- 校验禁用项：默认测试环境必须保持 fake/offline。

交付物：

- preflight 脚本输出规范（成功/失败字段）；
- preflight 执行记录文档（时间、环境、模型、结果摘要）。

## 5. Phase 5.2：Opt-in Real LLM Smoke Tests

目标：建立最小真实 LLM 烟雾测试，不影响默认 CI。

当前状态：**已完成 opt-in 机制与最小 smoke 用例框架**。

已落地内容：

- 新增 `pytest` marker：`real_llm`；
- 新增测试文件：`tests/test_real_llm_smoke_v52.py`；
- 默认 `python -m pytest -q` 不自动触发真实 LLM（需显式环境开关）；
- 新增脚本：`scripts/real_llm_smoke.ps1`；
- 新增报告模板：`docs/real_llm_smoke_report_template_v25.md`。
- 已补齐 `REAL_LLM_*` 与 NL2SQL 运行时 `LLM_*` 的对齐策略（测试中运行时映射，默认配置不改变）。
- 已收紧 NL2SQL smoke 断言：明确判断“真实命中 LLM”或“fallback 且有明确 fallback_reason”。

策略：

- 仅在显式开关启用时执行（例如本地手动命令或专用 CI job）；
- 覆盖最小链路：
  - Provider 基础调用；
  - NL2SQL preview 一条代表性查询；
  - 错误映射与 fallback 语义检查。

结果要求：

- 成功时记录 request_id、latency、token、cost；
- 失败时记录 error_type（auth/timeout/rate_limit/model/response）；
- 产出 smoke 报告，不改默认测试基线。

手动执行示例：

```bash
python -m pytest tests/test_real_llm_smoke_v52.py -m real_llm -q
```

环境变量门禁（全部为 true 才执行真实链路）：

- `REAL_LLM_SMOKE_ENABLED`
- `REAL_LLM_ACCEPTANCE_ENABLED`
- `REAL_LLM_PREFLIGHT_ENABLED`
- `REAL_LLM_PREFLIGHT_NETWORK_CHECK`

## 6. Phase 5.3：Token/Cost/Budget/Cache/Fallback 验收

目标：验证真实 provider 下的成本控制闭环。

验收点：

- token/cost 采集准确性（包含 prompt/completion/total/cost）；
- budget 软硬阈值行为（allow/warn/block/fallback）符合预期；
- cache 命中与未命中行为可观测，且不缓存高风险执行结果；
- fallback_to_mock 在预算阻断、调用异常、结构校验失败场景行为稳定。

交付物：

- 成本验收记录模板；
- 预算触发用例清单；
- cache 命中统计口径说明。

## 7. Phase 5.4：LLMJudge Opt-in 验收

目标：验证 LLMJudge 真实 provider 路径的可用性与可回退性。

验收点：

- `judge_provider=litellm` 时可生成结构化评分结果；
- JSON 非法/provider 不可用时，按配置执行 fallback_to_fake；
- `judge_fallback_to_fake=false` 时返回可控不可用状态，不抛 500；
- judge token/cost 可被 metrics 记录。

交付物：

- LLMJudge 验收记录文档；
- 失败归因模板（配置、网络、模型、响应结构、限流）。

## 8. Phase 5.5：文档与 release prep

目标：形成可发布但不夸大能力的文档收口。

内容建议：

- 新增“真实 LLM 可选验收报告”文档；
- README/AGENTS 只更新已完成事实，不宣称生产验收完成；
- release notes 增加“opt-in 验收已覆盖范围”与“仍未完成边界”。

## 9. 安全边界与执行原则

必须遵守：

- 不提交任何 API key、token、账号凭据到仓库；
- 真实 LLM 验收不进入默认 CI，不影响默认离线路径；
- 默认测试不调用真实 LLM；
- 不接真实外部 MCP 作为本阶段验收依赖；
- 不宣称真实 LLM 生产验收完成；
- 不宣称生产级 SSO、多租户、复杂 BI 已完成。

## 10. 建议执行顺序

建议按以下顺序推进：

1. Phase 5.1 preflight；
2. Phase 5.2 opt-in smoke；
3. Phase 5.3 成本/预算/缓存/降级闭环验收；
4. Phase 5.4 LLMJudge opt-in 验收；
5. Phase 5.5 文档与 release prep 收口。

以上顺序可在不改变默认离线稳定性的前提下，逐步提升真实 LLM 可选验收成熟度。

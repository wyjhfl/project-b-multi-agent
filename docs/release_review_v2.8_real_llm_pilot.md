# v2.8.0 Release Review：Controlled Real LLM Pilot

## 1. 评审范围

本次 review 聚焦 v2.8.0 的受控试点交付，不涉及真实外网 LLM 默认放开，不涉及 tag 与 GitHub Release 执行。

覆盖范围：

- `/llm/preflight` 状态观测与默认关闭语义
- 前端 `/llm` 页面
- acceptance_summary 统一口径
- budget/cache/fallback/LLMJudge opt-in 收敛
- 审计 / 日志 / 指标联动与脱敏边界

## 2. 功能完成度结论

### 2.1 preflight 与前端状态观测

- 已提供 `/llm/preflight` 结构化返回。
- 默认关闭时语义为 `disabled`，不阻断默认 fake/offline 路径。
- 前端 `/llm` 页面用于配置预检与风险可视化，不展示密钥原文，不提供密钥录入。

### 2.2 acceptance_summary 口径

- 已统一关键验收字段，覆盖 provider/model、真实调用尝试、fallback、tokens/cost、budget/cache、request_id、error_type。
- 默认不记录 prompt 原文与密钥原文。

### 2.3 budget/cache/fallback 与 LLMJudge

- budget hard limit 分支行为清晰，支持 fallback_to_mock 开关控制。
- LLMJudge 默认 FakeJudge，real provider 仍 opt-in。
- 不可用时返回 `llm_unavailable`，不抛 500。

### 2.4 审计/日志/指标联动

- 真实 LLM 尝试、成功、fallback、budget block 均可观测。
- 审计导出保持白名单与脱敏边界。
- 不导出 prompt 原文及密钥原文。

## 3. 验证结果

- `python -m pytest -q`：`730 passed, 4 skipped`
- 前端：`npm run lint`、`npm run build` 通过
- `docker compose config` 通过
- prod compose override：
  - 缺少必填变量时按预期失败
  - 注入临时变量后通过

## 4. 边界与风险声明

- v2.8.0 定位为 Controlled Real LLM Pilot，不等于真实 LLM 生产验收完成。
- 默认 pytest/CI 不调用真实 LLM；真实 LLM smoke 仍是 opt-in。
- 本次 review 未执行真实外网 LLM smoke（未提供真实密钥，也不应在默认流程执行）。
- 不宣称公网生产可直接上线。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 已完成。
- 不宣称真实外部 MCP 生产验收已完成。

## 5. 与 v2.7.0 发布关系

- v2.7.0 tag 与 GitHub Release 已发布完成。
- v2.7.0 tag 固定在 `2076111cb786df76a941ebf28f550f68f4131147`，本次未移动。
- 当前 main 超前 v2.7.0 tag，v2.8.0 为后续版本发布准备。

## 6. 结论

结论：**Go（可进入 v2.8.0 tag 决策）**。

前提：

- 保持默认 fake/offline 与默认 CI 无真实 LLM 调用。
- 继续执行密钥不入库、脱敏不回退、生产边界不夸大三条底线。

# RELEASE NOTES v2.5.0

## 1. Highlights

- 完成 v2.5.0 “真实 LLM 可选验收包”收口，覆盖 preflight、opt-in smoke、成本预算缓存降级与 LLMJudge opt-in 验收。
- 保持默认离线路径：fake/offline，默认 pytest 不调用真实 LLM。
- 新增可复用 smoke 报告模板，便于试点环境留痕与复盘。

## 2. Provider Preflight（Phase 5.1）

- 提供 `/llm/preflight` 结构化检查路径。
- 默认仅离线配置检查，不访问真实网络。
- 仅在显式 opt-in 且配置完整时允许 network check。

## 3. Opt-in Real LLM Smoke（Phase 5.2）

- 新增 `real_llm` marker 与 `tests/test_real_llm_smoke_v52.py`。
- 默认全量测试不会触发真实 LLM；未开启开关时自动 skip。
- 提供 `scripts/real_llm_smoke.ps1` 手动执行路径。

## 4. Token/Cost/Budget/Cache/Fallback（Phase 5.3）

- 验收摘要覆盖 token/cost/latency/cache_hit/budget_action/fallback。
- 离线测试覆盖预算阻断与 fallback 语义。
- runtime metrics 可观测预算与缓存摘要。

## 5. LLMJudge Opt-in Smoke（Phase 5.4）

- 新增 `tests/test_real_llm_judge_smoke_v54.py`，默认 opt-in gate。
- Judge provider 支持 base_url 对齐（优先 judge 专属配置）。
- bad case API 覆盖 fallback_to_fake 语义。

## 6. 默认离线与安全边界

- 默认 fake/offline，不提交 API key/token/账号凭据。
- 默认测试不调用真实 LLM，不接真实外部 MCP。
- 真实 LLM smoke 仅为 opt-in 验收，不等于生产验收完成。

## 7. 验证结果

- 本次 release prep 执行：版本断言、LLM preflight/smoke/judge 相关测试、全量 pytest、docker compose config/build。
- real_llm 用例在未 opt-in 环境下应为 skip，不应失败。

## 8. Known Boundaries

- 不宣称真实 LLM 生产验收已完成。
- 不宣称真实外部 MCP Server 生产验收已完成。
- 不宣称生产级 SSO、多租户、复杂 BI 已完成。
- 不宣称完整 LangGraph native Command resume 已完成。
- 不宣称生产可直接上线。

## 9. Upgrade Notes

- 版本号同步到 `2.5.0`：`pyproject.toml`、FastAPI `app.version`、`/health.version`、MCP client fallback 版本与相关测试断言。
- 文档同步 v2.5.0 验收包口径与边界说明。

## 10. Next phase

- 进入 v2.5.0 tag 决策阶段（本轮仅 release prep，不打 tag，不创建 GitHub Release）。

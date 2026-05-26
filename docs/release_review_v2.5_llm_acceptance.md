# v2.5.0 Release Review：LLM Optional Acceptance Pack

## 1. Scope

本次 review 聚焦 v2.5.0 的真实 LLM 可选验收包收口，不新增生产功能，不改变默认离线路径。

## 2. Changed modules

- 版本同步：`pyproject.toml`、`app/main.py`、`app/tools/mcp/stdio_client.py`、相关版本断言测试。
- 文档同步：`README.md`、`AGENTS.md`、`docs/llm_real_provider_acceptance_plan_v25.md`、`docs/real_llm_smoke_report_template_v25.md`。
- 发布文档：`RELEASE_NOTES_v2.5.0.md`、本 review 文档。

## 3. Verification matrix

- `python -m pytest tests/test_runtime_hardening_v055.py -q`
- `python -m pytest tests/test_llm_preflight_v51.py tests/test_real_llm_smoke_v52.py tests/test_real_llm_judge_smoke_v54.py -q`
- `python -m pytest tests/test_llm_acceptance_v53.py tests/test_llm_judge_v43.py tests/test_llm_provider_v41.py -q`
- `python -m pytest -q`
- `docker compose config`
- `docker compose build app frontend`

判定要求：默认环境下 `real_llm` 用例仅可 skip，不应触发真实外网调用。

## 4. Security / privacy boundary

- 不提交 API key、token、账号凭据；
- 默认 fake/offline，默认测试不调用真实 LLM；
- 真实 LLM smoke 必须显式 opt-in；
- 不接真实外部 MCP 作为默认验收依赖。

## 5. Known limitations

- 真实 LLM smoke 仅代表可选环境最小连通与语义检查，不等于生产验收完成；
- 不覆盖生产级 SSO、多租户、复杂 BI；
- 不宣称完整 LangGraph native Command resume 已完成；
- 项目仍是 production-grade engineering prototype，不能宣称生产可直接上线。

## 6. Go / No-Go

- 结论：**Go（建议进入 v2.5.0 tag 决策）**。
- 说明：本轮仅完成 release prep，不执行打 tag 与 GitHub Release。

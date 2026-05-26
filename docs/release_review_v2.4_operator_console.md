# v2.4.0 Release Review：Operator Console Pilot

## 1. Scope

本次 release prep 聚焦 v2.4.0 试点级运营台闭环，不新增后端核心能力方向，仅做版本同步、文档口径统一与发布前验证。

覆盖范围：

- 前端运营台壳与核心页面（Dashboard/Tasks/Approvals/Observability/Audit/Metrics/RBAC/Tools/NL2SQL）
- Docker 本地演示脚本（up/smoke/down）
- 后端版本号与健康检查版本同步

## 2. Changed Modules

- 版本与运行时：
  - `pyproject.toml`
  - `app/main.py`
  - `tests/test_runtime_hardening_v055.py`
  - `app/tools/mcp/stdio_client.py`
  - `tests/test_mcp_stdio_client_v31.py`
- 文档与发布：
  - `README.md`
  - `AGENTS.md`
  - `frontend/README.md`
  - `docs/operator_console_plan_v24.md`
  - `RELEASE_NOTES_v2.4.0.md`
  - `docs/release_review_v2.4_operator_console.md`

## 3. Verification Matrix

- 前端：
  - `npm run lint`
  - `npm run build`
- 后端：
  - `python -m pytest tests/test_runtime_hardening_v055.py -q`
  - `python -m pytest tests/test_nl2sql_v02.py tests/test_mcp_gateway_v03.py tests/test_auth_v20.py tests/test_rbac_v20.py -q`
  - `python -m pytest -q`
- Docker：
  - `docker compose config`
  - `docker compose build app frontend`
- 演示脚本：
  - `powershell -ExecutionPolicy Bypass -File scripts/demo_up.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/demo_smoke.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/demo_down.ps1`

## 4. Security / RBAC / Privacy Boundaries

- 默认鉴权与权限仍关闭（`auth_enabled=false`、`rbac_enabled=false`），保障离线演示可跑。
- 开启权限试点需显式设置 `AUTH_ENABLED=true`、`RBAC_ENABLED=true`。
- 前端 Tools 调用不绕过后端 ToolGateway / PolicyEngine / 审批链路。
- NL2SQL 默认 mock/fake，真实 LLM 仅可选配置，不进入默认验收。
- 不宣称真实 LLM 与真实外部 MCP Server 的生产验收完成。
- 不宣称生产级 SSO、多租户、复杂 BI 已完成。

## 5. Go / No-Go 结论

- 结论：**Go（建议进入 v2.4.0 tag 决策）**。
- 说明：本轮仅完成 release prep，不创建 tag，不创建 GitHub Release。

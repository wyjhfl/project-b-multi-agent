# RELEASE NOTES v2.4.0

## 1. Highlights

- 完成 v2.4.0 试点级运营台闭环，覆盖任务执行、审批、人审恢复、追踪审计、指标观测、工具目录与 NL2SQL 试点页。
- 默认路径保持离线可跑：`MCP_MODE=fake`、`auth_enabled=false`、`rbac_enabled=false`。
- 增加本地 Docker 演示脚本，支持一键启动、页面冒烟检查与清理。

## 2. Operator Console 页面范围

- Dashboard：运行总览与快捷入口。
- Tasks：任务列表、创建、详情、Trace 入口。
- Approvals：审批列表、详情、approve/reject/resume 闭环。
- Observability / Audit / Metrics：追踪、审计、指标聚合展示。
- RBAC：权限说明页（试点口径）。
- Tools：工具目录、筛选、最小调用验证。
- NL2SQL：preview/execute 试点页。

## 3. Approval Flow

- 支持 pending 审批检索、审批上下文查看、approve/reject、手动 resume。
- 高风险路径仍由后端策略与审批链路控制，前端不绕过 PolicyEngine。

## 4. Observability

- 支持任务 Trace 时间线查看。
- 支持审计事件筛选与详情查看。
- 支持 runtime/tasks/tools/cost 统一指标视图。

## 5. Tools + NL2SQL

- Tools 页面展示 `source/risk_level/permission_scope/is_local`，并支持最小调用验证。
- NL2SQL 页面支持 preview/execute，展示 SQL、warnings、guardrails、fallback、执行结果。
- NL2SQL 默认 mock/fake；真实 LLM 仅可选配置，不进入默认验收。

## 6. Docker Demo Scripts

- `scripts/demo_up.ps1`：构建并启动 app + frontend。
- `scripts/demo_smoke.ps1`：检查 `/api/health`、`/`、`/tasks`、`/approvals`、`/rbac`、`/tools`、`/nl2sql`、`/audit`、`/metrics`、`/observability`。
- `scripts/demo_down.ps1`：停止并清理容器。

## 7. Verification

- 前端：`npm run lint`、`npm run build`。
- 后端：指定子集 pytest + 全量 `python -m pytest -q`。
- Docker：`docker compose config`、`docker compose build app frontend`。
- 脚本：`demo_up` / `demo_smoke` / `demo_down`。

## 8. Known Boundaries

- 不宣称真实 LLM 生产验收已完成。
- 不宣称真实外部 MCP Server 生产验收已完成。
- 不宣称生产级 SSO、多租户、复杂 BI 已完成。
- 不宣称完整 LangGraph native Command resume 已完成。
- 项目仍为 production-grade engineering prototype，不等同生产可直接上线版本。

## 9. Upgrade Notes

- 版本号更新为 `2.4.0`（`pyproject.toml`、FastAPI `app.version`、`/health.version`、运行时断言测试）。
- 前端新增 Tools 与 NL2SQL 页面；导航和 Dashboard 快捷入口已更新。
- 如需权限试点，请显式启用 `AUTH_ENABLED=true` 与 `RBAC_ENABLED=true`。

## 10. Next Phase

- 进入 v2.4.x 收口与 v2.4.0 tag 决策阶段（本轮不打 tag）。

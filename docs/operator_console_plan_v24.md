# v2.4 规划：企业试点运营台与审批台（Project B）

## 1. 当前后端 API 能力盘点

### 1.1 任务与执行链路

- `POST /tasks`：创建任务，支持 `mode`、`generator`、`provider`、`fallback_to_mock`、`session_id`。
- `GET /tasks`、`GET /tasks/list`：任务列表。
- `GET /tasks/{task_id}`：任务详情。
- `GET /tasks/{task_id}/trace`：任务 Trace 事件。

### 1.2 审批与恢复执行

- `GET /approvals`：审批列表（支持状态筛选）。
- `GET /approvals/{approval_id}`：审批详情。
- `POST /approvals/{approval_id}/approve`：审批通过（可 `auto_resume`）。
- `POST /approvals/{approval_id}/reject`：审批拒绝（触发任务取消）。
- `GET /approvals/summary`：审批概览（pending/approved/rejected/expired）。
- `GET /approvals/{approval_id}/context`：审批上下文（任务、payload、timeline、可执行动作）。
- `POST /approvals/{approval_id}/resume`：手动 resume。

### 1.3 审计与可观测

- `GET /audit/events`：审计事件查询（支持多条件筛选）。
- `GET /audit/events/{event_id}`：审计事件详情。
- `GET /metrics/runtime`：运行时指标总览（含 LLM budget/cache 概览）。
- `GET /metrics/cost/summary`：token/cost 聚合。
- `GET /metrics/tools/summary`：工具调用聚合。
- `GET /metrics/tasks/summary`：任务状态聚合。

### 1.4 工具与 NL2SQL

- `GET /tools`：工具列表（source/risk_level/permission_scope）。
- `POST /tools/{tool_name}/call`：直接调用工具（走 policy）。
- `POST /nl2sql/preview`：SQL 预览。
- `POST /nl2sql/execute`：SQL 执行。
- `POST /nl2sql/eval`：离线评测。

### 1.5 认证授权现状

- 已有 JWT + RBAC 依赖链路，关键接口通过 `require_permission(...)` 接入。
- 默认 `auth_enabled=false`、`rbac_enabled=false`，可直接演示。
- 开启后可按角色控制访问（admin/operator/viewer/auditor）。

---

## 2. v2.4 前端目标（试点导向）

目标不是继续扩后端功能，而是把现有能力整理为“可演示、可试点、可操作”的前端工作台：

- 运营台：任务创建、结果查看、失败排查。
- 审批台：高风险审批、approve/reject/resume 闭环。
- 任务详情：状态、结果、错误、上下文。
- Trace/Audit：执行轨迹与合规留痕可视化。
- Metrics：任务/工具/成本/预算/缓存状态可见。
- LLM 成本治理：展示 token、cost、budget_status、cache_hit/miss。

---

## 3. 页面信息架构（IA）

### 3.1 一级导航

- 工作台（Dashboard）
- 任务中心（Tasks）
- 审批中心（Approvals）
- 追踪与审计（Trace & Audit）
- 指标中心（Metrics）
- 工具与 NL2SQL（Tools & NL2SQL）

### 3.2 二级页面建议

- 工作台
  - 今日概览卡片：任务数、待审批数、失败数、工具失败率。
- 任务中心
  - 任务列表页
  - 任务详情页（基本信息、result、error、trace）
- 审批中心
  - 待审批列表页
  - 审批详情页（上下文、风险信息、动作按钮）
- 追踪与审计
  - Trace 时间线页（按 task_id）
  - Audit 检索页（按 event_type/actor/outcome/severity）
- 指标中心
  - runtime 总览页
  - cost/tools/tasks 聚合页
- 工具与 NL2SQL
  - 工具目录与手动调用页
  - NL2SQL preview/execute 调试页

---

## 4. 核心用户流程

### 4.1 创建任务

1. 在任务中心填写 query、mode、generator/provider（可选）。
2. 调用 `POST /tasks`。
3. 跳转任务详情，展示 status/result/error。

### 4.2 高风险任务进入审批

1. 任务执行命中 high risk，后端返回 `waiting_approval`（任务详情可见）。
2. 前端轮询/刷新审批列表：`GET /approvals?status=pending`。
3. 审批台显示 pending 审批卡片。

### 4.3 审批通过/拒绝

- 通过：`POST /approvals/{id}/approve`（`auto_resume=true` 默认）。
- 拒绝：`POST /approvals/{id}/reject`（任务进入 `cancelled`）。

### 4.4 resume 后查看结果

1. approve 后若自动 resume，读取 `resume_result`。
2. 若需要手动恢复，调用 `POST /approvals/{id}/resume`。
3. 回到 `GET /tasks/{task_id}` 查看最终状态与结果。

### 4.5 查看 trace / audit / metrics

- Trace：`GET /tasks/{task_id}/trace`。
- Audit：`GET /audit/events` + `GET /audit/events/{event_id}`。
- Metrics：`GET /metrics/runtime`、`/metrics/cost/summary`、`/metrics/tools/summary`、`/metrics/tasks/summary`。

---

## 5. API 对接清单（按页面）

### 5.1 工作台

- `GET /metrics/runtime`
- `GET /approvals/summary`
- `GET /metrics/tasks/summary`

### 5.2 任务中心

- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/trace`

### 5.3 审批中心

- `GET /approvals?status=pending`
- `GET /approvals/{approval_id}`
- `GET /approvals/{approval_id}/context`
- `POST /approvals/{approval_id}/approve`
- `POST /approvals/{approval_id}/reject`
- `POST /approvals/{approval_id}/resume`

### 5.4 追踪与审计

- `GET /tasks/{task_id}/trace`
- `GET /audit/events`
- `GET /audit/events/{event_id}`

### 5.5 指标中心

- `GET /metrics/runtime`
- `GET /metrics/cost/summary`
- `GET /metrics/tools/summary`
- `GET /metrics/tasks/summary`

### 5.6 工具与 NL2SQL

- `GET /tools`
- `POST /tools/{tool_name}/call`
- `POST /nl2sql/preview`
- `POST /nl2sql/execute`

---

## 6. 权限 / RBAC 设计（admin/operator/viewer/auditor）

### 6.1 角色定位

- `admin`：全权限（配置、任务、审批、审计、指标）。
- `operator`：任务执行与审批操作主体。
- `viewer`：只读查看任务、审批结果、指标。
- `auditor`：审计与追踪优先，重点查看 audit/trace/metrics。

### 6.2 页面级建议

- 工作台：admin/operator/viewer/auditor 全可见。
- 任务中心：
  - 创建任务：admin/operator
  - 查看列表与详情：全角色
- 审批中心：
  - approve/reject/resume：admin/operator
  - 审批只读：viewer/auditor
- 追踪与审计：
  - audit 全量筛查：admin/auditor 优先
  - viewer 仅只读受限查询（按后端权限实现）
- 指标中心：全角色只读，admin 可扩展运维视角。

---

## 7. 前端技术建议（Next.js vs Vite React）

### 推荐：Next.js

推荐原因（结合当前仓库与试点目标）：

- 现有企业试点规划文档已使用 Next.js 口径，团队语义一致。
- 页面路由、布局、权限守卫与 API proxy 能更快形成“运营台 + 审批台”结构。
- 便于后续扩展 SSR/中间层（如 token 注入、后端地址隔离、环境区分）。
- 对 Docker 部署友好，试点演示更稳定。

Vite React 可作为轻量备选，但 v2.4 目标是“可试点交付”，优先选 Next.js。

---

## 8. 验收标准（v2.4 Planning 对齐）

- 不依赖真实 LLM：默认 fake/offline 路径可完整演示。
- 不依赖真实 MCP：默认 `MCP_MODE=fake` 可演示工具与审批流程。
- Docker Compose 可本地试点：后端可一键启动并被前端接入。
- 默认 auth/rbac 关闭仍可演示核心流程。
- 开启 auth/rbac 后，角色权限与页面动作能正确收敛。
- 核心流程可演示：任务创建 → 审批决策 → resume → trace/audit/metrics 可见。

---

## 9. 明确不做（v2.4 范围外）

- 不做复杂 BI 报表系统。
- 不做多租户隔离模型。
- 不做生产级 SSO（如企业统一身份平台深度对接）。
- 不接真实外部系统（外部 MCP、外部业务系统、外部工单系统）。

---

## 10. 交付建议（规划到实现的最小切分）

- v2.4.1：前端壳 + 导航 + 任务中心最小闭环。
- v2.4.2：审批台闭环（approve/reject/resume + context）。
- v2.4.3：Trace/Audit/Metrics 聚合展示。
- v2.4.4：RBAC 页面收敛与 Docker 本地演示脚本。

该切分确保“每步可演示、每步可回归”，避免一次性大前端改造风险。

---

## 11. v2.4.3 已完成范围（状态同步）

- 已完成 Trace 查询页：支持按 `task_id` 查询时间线。
- 已完成 Audit 查询页与详情页：支持 `event_type` / `task_id` / `severity` / `outcome` 基础筛选与详情查看。
- 已完成 Metrics 聚合展示：覆盖 runtime、tasks、tools、cost、llm_budget、llm_cache 的紧凑卡片与表格展示。
- 已完成任务详情与审批详情到 Trace/Audit 的联动入口。

## 12. 仍保持的边界

- 不做复杂 BI 可视化大屏。
- 不做多租户隔离能力。
- 不做生产级 SSO。

## 13. v2.4.4 已完成范围（状态同步）

- 已补充 RBAC 试点说明页：展示默认演示模式（auth/rbac 默认关闭）与启用后的角色边界。
- 已补充本地 Docker 演示脚本：
  - `scripts/demo_up.ps1`
  - `scripts/demo_smoke.ps1`
  - `scripts/demo_down.ps1`
- 演示脚本覆盖页面可达性检查：`/`、`/tasks`、`/approvals`、`/audit`、`/metrics`、`/observability` 以及 `/api/health`。

## 14. v2.4 阶段小结

- v2.4.1：前端壳与任务中心最小闭环 ✅
- v2.4.2：审批台闭环（approve/reject/resume）✅
- v2.4.3：Trace/Audit/Metrics 聚合展示 ✅
- v2.4.4：RBAC 试点说明与 Docker 本地演示脚本 ✅
- v2.4.5：Tools + NL2SQL 试点页 ✅

## 15. v2.4.5 已完成范围（状态同步）

- 已补齐 Tools API client 与页面：
  - 工具目录展示 `name/description/source/risk_level/permission_scope/is_local`
  - 支持按 `source/risk_level` 筛选
  - 支持最小 JSON arguments 调用验证
- 已补齐 NL2SQL API client 与页面：
  - 支持 `preview` 与 `execute`
  - 展示 `sql/confidence/selected_tables/warnings/guardrails/fallback/result/error`
  - 页面仅展示后端返回的脱敏内容，不展示原始 PII
- 已补强本地演示脚本检查范围：
  - 新增 `/rbac`、`/tools`、`/nl2sql` 页面可达性检测

## 16. v2.4.5 边界说明

- 默认仍为离线演示路径，不接真实 LLM。
- 默认不接真实外部 MCP Server。
- 当前仍不做生产级 SSO、多租户、复杂 BI。

## 17. v2.4.0 release prep 统一口径

- v2.4.0 已完成试点级运营台闭环（Dashboard / Tasks / Approvals / Trace / Audit / Metrics / RBAC / Tools / NL2SQL + Docker demo scripts）。
- 默认仍为离线演示路径，不依赖真实 LLM，不依赖真实外部 MCP Server。
- Tools 页面仅作为试点验证入口，前端调用不会绕过后端 ToolGateway / PolicyEngine / 审批链路。
- NL2SQL 页面默认 mock/fake；真实 LLM 仅可选配置，不进入默认验收。
- 当前仍不做生产级 SSO、多租户、复杂 BI，不宣称生产可直接上线。

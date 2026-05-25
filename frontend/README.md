# Project B 前端（v2.4）

本目录是 Project B 的试点级运营台前端，基于 Next.js + TypeScript + App Router。

## 本地开发

```bash
npm install
npm run dev
```

- 默认访问地址：[http://localhost:3000](http://localhost:3000)
- 默认后端地址：`http://localhost:8000`
- 如需修改后端地址，可设置 `NEXT_PUBLIC_API_BASE_URL`

## Docker Compose 运行

在仓库根目录执行：

```bash
docker compose up -d app frontend
```

- 前端服务使用 `NEXT_PUBLIC_API_BASE_URL=http://app:8000`
- 容器内 `/api/*` 代理会转发到 `app` 服务

停止服务：

```bash
docker compose down
```

## /api/health 代理验证

在宿主机执行：

```bash
curl http://localhost:3000/api/health
```

预期：返回后端 `/health` 的 JSON 响应，且不是前端 404。

## 当前页面范围（v2.4.5）

- Dashboard（运行概览）
- Tasks list（任务列表）
- Task create（任务创建）
- Task detail + trace（任务详情与时间线）
- Approvals list（支持 pending / approved / rejected / all 筛选）
- Approval detail（支持 approve / reject / resume 闭环动作）
- Observability（按 task_id 查询 Trace）
- Audit（审计筛选列表 + 审计详情）
- Metrics（runtime / tasks / tools / cost / llm_budget / llm_cache 聚合展示）
- RBAC 说明页（展示默认演示模式与试点角色边界）
- Tools 试点页（工具目录 + 最小调用验证）
- NL2SQL 试点页（preview / execute + guardrails/warnings/fallback 展示）

## v2.4.5 本地验证建议

1. 启动后端（仓库根目录）：
   - `docker compose up -d app`
2. 启动前端（frontend 目录）：
   - `npm run dev`
3. 浏览器验证页面：
   - `http://localhost:3000/tools`
   - `http://localhost:3000/nl2sql`
   - `http://localhost:3000/rbac`
   - `http://localhost:3000/metrics`
4. 验证联动入口：
   - Dashboard 可进入工具目录和 NL2SQL
   - 任务详情可跳转 Trace / Audit
   - 审批详情可跳转关联任务 Trace / Audit

## RBAC 试点说明

- 默认仍为演示路径：`AUTH_ENABLED=false`、`RBAC_ENABLED=false`
- 若需启用权限控制，请显式设置：
  - `AUTH_ENABLED=true`
  - `RBAC_ENABLED=true`
- 当前不实现生产登录系统，不提供 SSO、多租户能力。

## 当前边界

- 默认离线可跑，不依赖真实 LLM。
- 默认不依赖真实外部 MCP Server。
- 当前不做生产级 SSO、多租户、复杂 BI。

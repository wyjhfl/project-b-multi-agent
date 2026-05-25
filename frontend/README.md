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

## 当前页面范围（v2.4.3）

- Dashboard（运行概览）
- Tasks list（任务列表）
- Task create（任务创建）
- Task detail + trace（任务详情与时间线）
- Approvals list（支持 pending / approved / rejected / all 筛选）
- Approval detail（支持 approve / reject / resume 闭环动作）
- Observability（按 task_id 查询 Trace）
- Audit（审计筛选列表 + 审计详情）
- Metrics（runtime / tasks / tools / cost / llm_budget / llm_cache 聚合展示）

## v2.4.3 本地验证建议

1. 启动后端（仓库根目录）：
   - `docker compose up -d app`
2. 启动前端（frontend 目录）：
   - `npm run dev`
3. 浏览器验证页面：
   - `http://localhost:3000/metrics`
   - `http://localhost:3000/audit`
   - `http://localhost:3000/observability`
4. 随机进入一个任务详情或审批详情，验证：
   - 可跳转到 Trace / Audit 页面
   - 页面展示无空白、无明显错位

## 当前边界

- 默认离线可跑，不依赖真实 LLM。
- 默认不依赖真实外部 MCP Server。
- 当前不做复杂 BI、多租户、生产级 SSO。

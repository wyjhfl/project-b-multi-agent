# Project B 前端（v2.4.1）

本目录是 Project B 的试点级运营台前端，基于 Next.js + TypeScript + App Router。

## 运行方式

### 本地开发

```bash
npm install
npm run dev
```

默认打开 [http://localhost:3000](http://localhost:3000)。

### 环境变量

- `NEXT_PUBLIC_API_BASE_URL`：后端 API 基地址  
  - 本地开发默认值：`http://localhost:8000`
  - Docker Compose 场景建议：`http://app:8000`

## 当前页面范围（v2.4.1）

- Dashboard（运行概览）
- Tasks list（任务列表）
- Task create（任务创建）
- Task detail + trace（任务详情与时间线）
- Approvals 轻量入口（仅展示待审批概览，不含完整动作页）
- Metrics 占位入口

## 约束说明

- 默认离线可跑，不依赖真实 LLM。
- 默认不依赖真实外部 MCP Server。
- 当前不做复杂 BI、多租户、生产级 SSO。

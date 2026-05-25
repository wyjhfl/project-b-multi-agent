# Enterprise Pilot Plan - v2.0

## 目标

从 production-grade prototype 升级为**企业内网试点系统**。v2.0 不再以"多 Agent 炫技"为主，而是以**企业可控执行、审批、审计、评测、可观测**为主。

## 选型

| 领域 | 选型 | 说明 |
|------|------|------|
| 关系数据库 | PostgreSQL | 替代 SQLite，支持并发、事务、JSONB |
| 缓存 / 会话 | Redis | 审批状态缓存、session 存储、rate limiting |
| 认证授权 | JWT + RBAC | 替代无认证，支持角色 (admin / operator / viewer) |
| LLM 接入 | LiteLLM | 真实 LLM Provider，支持 OpenAI / Azure / 本地模型 |
| 前端 | Next.js | 运营台 (查询 + 指标看板) + 审批台 (审批 + 审计日志) |
| Agent 编排 | LangGraph checkpoint / interrupt | 替代当前顺序流，支持持久化 checkpoint 和 interrupt/resume |
| MCP 工具 | Real MCP stdio client | 替代 FakeMCPClient，接入真实 MCP Server |
| 可观测 | OpenTelemetry | trace / metrics / logs 统一导出 |

## 阶段

### Phase 1: PostgreSQL / Redis / Auth / RBAC

**目标**: 基础设施生产化

| 任务 | 说明 |
|------|------|
| PostgreSQL 迁移 | TaskStore / ApprovalStore / AuditStore / MetricsStore 全部迁移到 PostgreSQL，SQLite 保留为 fallback |
| Redis 集成 | 审批状态缓存、session 存储、API rate limiting |
| JWT 认证 | /auth/login / /auth/refresh / /auth/me，Bearer Token |
| RBAC 授权 | admin (全权限) / operator (创建任务 + 审批) / viewer (只读)，PolicyEngine 集成角色检查 |
| 环境配置 | DATABASE_URL / REDIS_URL / JWT_SECRET / LITELLM_API_KEY 通过 pydantic-settings 管理 |
| Docker Compose | PostgreSQL + Redis + App 三容器编排 |

**验收标准**:

- 所有 Store 操作通过 PostgreSQL 完成，SQLite fallback 可选
- JWT 认证保护所有 API (/health 除外)
- RBAC 角色权限正确: viewer 不能创建任务，operator 不能管理用户
- Redis 缓存命中率和 rate limiting 正常工作
- Docker Compose 一键启动，513+ 测试全部通过

**Phase 1 Foundation 完成状态 (v2.0.1)**:

| 任务 | 状态 | 说明 |
|------|------|------|
| PostgreSQL 迁移 | Foundation 完成 | PostgresTaskStore / PostgresApprovalStore / PostgresAuditStore / PostgresMetricsStore 已实现，Store Factory 根据 storage_backend 切换，默认 sqlite |
| Redis 集成 | 基础完成 | NoopRedisClient + get_redis_client() + check_redis_health()，redis_enabled=false 时不连接 |
| JWT 认证 | 完成 | PyJWT + bcrypt，POST /auth/login + GET /auth/me，auth_enabled=false 兼容 |
| RBAC 授权 | 完成 | 4 角色 (admin / operator / viewer / auditor) + ROLE_HIERARCHY + ENDPOINT_PERMISSIONS + require_roles / require_permission，rbac_enabled=false 兼容 |
| 环境配置 | 完成 | pydantic-settings 管理 9 个新配置项 |
| Docker Compose | 完成 | PostgreSQL 16-alpine + Redis 7-alpine + App 三容器编排 |
| Alembic 迁移 | 完成 | 7 张表初始迁移 (users / task_runs / approval_requests / audit_events / runtime_task_metrics / runtime_tool_metrics / runtime_token_usage) |

**Phase 1.1 Integration Cleanup（v2.0.1 内部阶段）**:

- Store Factory 已接入 `app.main` 主链路 getter；`reset_runtime_for_test()` 后会按当前配置重新创建 store。
- RBAC 已接入关键 API：tasks、approvals、approval resume、audit events、tools call、metrics；`/health` 和 `/auth/*` 不加权限。
- Docker app 启动改为 `scripts/start_app.py`：先运行 demo DB 初始化，PostgreSQL 模式下执行 `alembic upgrade head`，再启动 `uvicorn app.main:app`。
- JWT 默认开发 secret 加长到 32+ 字符，仅用于本地开发，不引入真实 secret。
- 默认兼容口径不变：`auth_enabled=false`、`rbac_enabled=false`、`storage_backend=sqlite`；PostgreSQL 通过 `STORAGE_BACKEND=postgres` + 非空 `DATABASE_URL` 启用。

**Phase 1.1.1 Docker Startup & Release Polish（v2.0.1 内部阶段）**:

- Dockerfile 已复制 `alembic.ini` 和 `alembic/`，保证容器内 startup migration 可找到迁移文件。
- `GET /tools` 已接入 `tools:read`，viewer/auditor/operator/admin 均可读工具列表；工具调用仍需 `tools:call`。
- 正式 release 版本号统一为 `v2.0.1`，测试口径统一为 `513+`。
- 最近发布验证：`513 passed`、`docker compose config passed`、`docker compose build app passed`。

**关键设计决策**:
- auth_enabled=false / rbac_enabled=false / redis_enabled=false / storage_backend=sqlite 为默认值，保证旧 API 和既有测试不破
- InMemoryUserStore 本地可测试，默认 admin 密码通过 DEV_ADMIN_PASSWORD 环境变量设置
- PostgreSQL Store 实现最小 CRUD，与 SQLite store 返回结构一致；v2.0.1 后主链路通过 Store Factory 创建，默认仍走 SQLite，postgres 配置开启后走 PostgreSQL
- passlib[bcrypt] 与新版 bcrypt 不兼容，已切换为直接使用 bcrypt 库

### Phase 2: 真实 LangGraph checkpoint / interrupt / resume（尚未开始）

**目标**: Agent 编排生产化

| 任务 | 说明 |
|------|------|
| LangGraph checkpoint | PostgreSQL 持久化 checkpoint，任务中断后可恢复 |
| interrupt / resume | 高风险操作触发 interrupt -> 审批通过后 resume，替代当前 PolicyEngine 拦截 |
| checkpoint 清理 | 过期 checkpoint 自动清理策略 |
| 并发安全 | 同一任务同时只有一个 resume 执行 |

**验收标准**:

- 任务中断后重启服务可恢复执行
- interrupt -> approve -> resume 链路完整
- 并发 resume 不重复执行
- checkpoint 清理不影响活跃任务
- 513+ 测试全部通过

### Phase 3: 真实 MCP stdio client

**目标**: 工具层生产化

| 任务 | 说明 |
|------|------|
| StdioMCPClient 实现 | 真实 MCP stdio 协议: spawn MCP Server -> stdin/stdout JSON-RPC -> 工具发现 + 调用 |
| MCP Server 管理 | MCP_MODE=real 下自动发现和注册 MCP Server 工具 |
| 错误恢复 | MCP Server 崩溃后自动重启，超时后 fallback |
| 工具沙箱 | MCP Server 在受限环境中运行，限制文件系统和网络访问 |

**验收标准**:

- 真实 MCP Server 工具可通过 ToolGateway 调用
- MCP Server 崩溃后自动恢复
- 工具调用超时有 fallback
- FakeMCPClient 仍可用于开发和测试
- 513+ 测试全部通过

### Phase 4: LiteLLM 真实 provider + guardrails

**目标**: LLM 层生产化

| 任务 | 说明 |
|------|------|
| LiteLLMProvider 实现 | 接入 OpenAI / Azure / 本地模型，支持 fallback_to_mock |
| NL2SQL 真实生成 | LLMNL2SQLGenerator 使用真实 LLM 生成 SQL |
| LLM-as-Judge | LLMJudgeProvider 使用真实 LLM 打分 |
| Guardrails | 输入/输出 guardrails: PII 检测、SQL 注入二次校验、输出格式校验 |
| 成本控制 | LiteLLM cost tracking + 预算限制 + 告警 |

**验收标准**:

- NL2SQL 使用真实 LLM 生成 SQL，SQLGuard 仍有效拦截危险 SQL
- LLM-as-Judge 打分与 FakeJudge 结果偏差 < 20%
- PII 检测和 SQL 注入二次校验正常工作
- 成本超预算自动降级到 mock
- 513+ 测试全部通过

### Phase 5: Next.js 运营台和审批台

**目标**: 前端生产化

| 任务 | 说明 |
|------|------|
| 运营台 | 查询输入 -> 结果展示 -> 图表渲染 -> 历史记录 |
| 审批台 | 待审批列表 -> 审批/拒绝 -> 审计日志查看 |
| 指标看板 | GMV / 退款率 / 订单量 实时指标 + 趋势图 |
| 用户管理 | 登录 / 角色管理 / 权限配置 |

**验收标准**:

- 运营台可完成查询 -> 结果 -> 图表全流程
- 审批台可完成审批/拒绝 -> 任务恢复/取消
- 指标看板数据与 API 一致
- JWT 认证 + RBAC 权限正确
- 前端构建产物可 Docker 部署

### Phase 6: OpenTelemetry / Docker Compose / CI hardening

**目标**: 运维生产化

| 任务 | 说明 |
|------|------|
| OpenTelemetry | trace / metrics / logs 统一导出，支持 Jaeger / Prometheus / Loki |
| Docker Compose | PostgreSQL + Redis + App + Frontend + MCP Server 五容器编排 |
| CI hardening | GitHub Actions 增加 lint / type check / security scan / integration test |
| 健康检查 | /health 增加 PostgreSQL / Redis / MCP Server 连通性检查 |
| 备份恢复 | PostgreSQL 定期备份 + 恢复脚本 |

**验收标准**:

- OpenTelemetry 数据可被 Jaeger / Prometheus / Loki 采集
- Docker Compose 一键启动完整系统
- CI 包含 lint / type check / security scan / integration test
- /health 正确反映所有依赖状态
- 备份恢复脚本可用
- 513+ 测试全部通过

## 核心原则

1. **企业可控 > Agent 自治**: v2.0 的核心价值不是"Agent 多聪明"，而是"企业对 Agent 行为有多少控制力"
2. **审批 > 自动执行**: 高风险操作必须经过人工审批，不是自动执行
3. **审计 > 速度**: 每一步操作都有审计记录，宁可慢一点也要可追溯
4. **评测 > 炫技**: Trajectory Eval / BadCase Eval / LLM-as-Judge 确保行为正确，不是展示能力
5. **可观测 > 黑箱**: OpenTelemetry 全链路追踪，不是黑箱执行
6. **渐进式 > 大爆炸**: 每个 Phase 独立可交付，不依赖后续 Phase

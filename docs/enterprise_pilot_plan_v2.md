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
- Docker Compose 一键启动，432+ 测试全部通过

### Phase 2: 真实 LangGraph checkpoint / interrupt / resume

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
- 432+ 测试全部通过

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
- 432+ 测试全部通过

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
- 432+ 测试全部通过

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
- 432+ 测试全部通过

## 核心原则

1. **企业可控 > Agent 自治**: v2.0 的核心价值不是"Agent 多聪明"，而是"企业对 Agent 行为有多少控制力"
2. **审批 > 自动执行**: 高风险操作必须经过人工审批，不是自动执行
3. **审计 > 速度**: 每一步操作都有审计记录，宁可慢一点也要可追溯
4. **评测 > 炫技**: Trajectory Eval / BadCase Eval / LLM-as-Judge 确保行为正确，不是展示能力
5. **可观测 > 黑箱**: OpenTelemetry 全链路追踪，不是黑箱执行
6. **渐进式 > 大爆炸**: 每个 Phase 独立可交付，不依赖后续 Phase

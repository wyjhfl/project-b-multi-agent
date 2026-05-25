# AGENTS.md — 仓库级规则

## 语言

- 所有文档和注释使用**简体中文**

## 安全

- **禁止提交任何密钥、Token、API Key** 到仓库
- 敏感配置通过 `.env` 文件管理，`.env` 已在 `.gitignore` 中排除
- 使用 `.env.example` 提供配置模板

## 版本路线

| 版本 | 里程碑 | 核心交付 |
|------|--------|---------|
| **v0.1** | Harness Core | Harness 五层管线 + AgentKernel 主链路 + KeywordPlanner + SQLite demo + 5 个本地工具 |
| **v0.2** | NL2SQL Eval Harness | SchemaMetadataExtractor / SchemaPruner / SQLGuard / MockNL2SQLGenerator / LLMNL2SQLGenerator / SQLiteReadOnlyExecutor / SQLResultFormatter / ChartPlanner + 可插拔 LLM Provider |
| **v0.3** | MCP Gateway + MultiTool + MultiAgent Role Orchestration | FakeMCPClient + StdioMCPClient / MultiToolPipeline / MultiAgentOrchestrator（确定性多角色编排）/ Task Persistence + Docker |
| **v0.4** | HITL + Security + Audit | ApprovalStore / ApprovalResumeService / PromptInjectionGuard / OperationWhitelist / AuditRecorder + SQLiteAuditStore |
| **v0.5** | Runtime Hardening | RuntimeMetricsRecorder + SQLiteMetricsStore / 30+ BadCase + FakeJudge / ShortTermMemory + SkillRegistry + SelfCheckEngine / Cost Dashboard API / Runtime Snapshot |
| **v1.0** | Release | 全部能力稳定交付，370 个测试，生产级工程化框架 |
| **v1.1** | Credibility & Eval Hardening | 表述对齐 / TrajectoryEvaluator / Multi-Agent eval 扩展 / 最小 LangGraph StateGraph 骨架 |
| **v1.1.1** | Documentation & Eval Precision Cleanup | README/docs 口径统一 / expected_tools 补强 / HITL/Security eval semantic split / RiskIntentGuard / interview_guide / 432+ tests |
| **v2.0.1** | Phase 1 Foundation + Integration Cleanup | SQLAlchemy + Alembic + psycopg / Redis + NoopRedisClient / JWT Auth + bcrypt / RBAC 接入关键 API / Store Factory 接入 app.main / Docker startup migration / Dockerfile Alembic 修复 / tools:read / 553+ tests |
| **v2.1.0** | Graph Runtime Adapter | Phase 2.1 GraphCheckpointStore / Phase 2.2 GraphRuntimeAdapter feature flag / Phase 2.3 graph interrupt -> approval mapping / Phase 2.4 GraphResumeAdapter / Phase 2.5 release cleanup + failure-path hardening; default graph_runtime_enabled=false; legacy behavior unchanged; 553+ tests |
| **v2.2.0** | MCP Stdio Runtime Hardening | Phase 3.1 stdio protocol skeleton / Phase 3.2 tools/list mapping / Phase 3.3 tools/call integration / Phase 3.4 lifecycle hardening / Phase 3.5 release cleanup; default MCP_MODE=fake unchanged; real mode requires explicit command + allowlist; 582+ tests |
| **v2.3.0** | LLM Provider + Guardrails Runtime | Phase 4.1 LiteLLMProvider 硬化 / Phase 4.2 NL2SQL 真实 LLM 生成链路 + 结构化校验 + fallback / Phase 4.3 可选 LLMJudgeProvider + 评测元数据 / Phase 4.4 Guardrails 编排 + PII 脱敏防泄漏 / Phase 4.5 预算+缓存+降级闭环；默认 fake/offline，默认测试不调用真实 LLM；636+ tests |

## Known Pitfalls

- **Multi-Agent 是规则型多角色编排**：Coordinator / Analyst / Executor / Reviewer 当前是规则驱动边界划分，不是完全自治多 Agent。不要在文档或代码中包装为"自治多 Agent"。
- **StdioMCPClient 已有 real protocol path**：支持 subprocess stdio + JSON-RPC initialize/tools/list/tools/call + lifecycle hardening；默认仍 `MCP_MODE=fake`，real 模式需显式配置 command/allowlist，且当前验收基于 fake stdio server fixture。
- **LLMJudgeProvider 已支持可选真实 provider 路径**：默认仍 fake/offline，默认测试不调用真实 LLM。不要在文档中宣称真实 LLM 生产验收已完成。
- **LangGraph runtime 边界**：v1.1 只有最小 StateGraph smoke；Phase 2 已实现默认关闭的 graph checkpoint / interrupt / resume adapter 最小闭环，仅支持 graph_runtime_enabled=true 下 graph_keyword 单工具 approval resume。不要声称已实现完整 LangGraph native Command resume。
- **不要在文档中夸大为"生产环境即插即用"**：本项目是 production-grade engineering prototype，不可直接用于生产部署。
- **auth_enabled 默认 false**：JWT / RBAC 默认不启用，旧 API 不需要 token。不要在默认配置下要求 token。
- **rbac_enabled 默认 false**：即使关键 API 已接入 require_permission，RBAC 角色检查默认仍不启用。企业试点时设置 AUTH_ENABLED=true + RBAC_ENABLED=true。
- **storage_backend 默认 sqlite**：PostgreSQL Store 已实现但默认不启用。不要在默认配置下要求 PostgreSQL 可用。
- **redis_enabled 默认 false**：Redis 默认不连接，NoopRedisClient 不抛异常。不要在默认配置下要求 Redis 可用。
- **InMemoryUserStore 是本地测试实现**：不持久化，重启后用户数据丢失。企业试点需要 PostgreSQL UserStore。
- **PostgreSQL Store 可通过配置启用**：v2.0.1 后 app.main 主链路通过 Store Factory 创建 store；默认仍 storage_backend=sqlite。设置 STORAGE_BACKEND=postgres 且 DATABASE_URL 非空时使用 PostgreSQL Store。

## 开发规范

- 改动后运行最小测试：`python -m pytest`
- 保持模块间低耦合，通过接口通信
- 新增模块必须有对应的 `__init__.py`
- Pydantic 模型放在 `app/models/schemas.py`
- Harness 组件放在 `app/harness/` 对应子模块
- 所有新增能力必须有测试

## 不要做的事

- 不要在默认测试与默认配置下依赖真实外部 MCP Server
- 不要在默认测试中调用真实 LLM API
- 不要做前端审批 UI
- 不要重写 Harness Runtime
- 不要把规则型 Multi-Agent 包装成自治多 Agent
- 不要在默认配置下启用 auth_enabled / rbac_enabled / redis_enabled
- 不要删除 SQLite demo 数据和 SQLite store 实现
- 不要在 Phase 1 实现 LangGraph checkpoint / interrupt
- 不要宣称完整 LangGraph native Command resume、真实 MCP、真实 LLM、前端审批 UI 已完成

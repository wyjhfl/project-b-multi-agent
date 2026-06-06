# AGENTS.md — 仓库级规则

## v4.4 Phase 24.1 Real integration readiness matrix（当前推进中）

- 规划文档：`docs/v4_4_real_integration_landing_plan.md`。
- 已新增只读矩阵脚本：`scripts/real_integration_readiness_matrix.py`。
- 已新增测试：`tests/test_real_integration_readiness_matrix_v441.py`。
- 默认输出目录：`docs/reports/real_integration_readiness/`。
- 覆盖真实 LLM、PostgreSQL、Redis、真实 MCP Server 的 opt-in 条件、本地证据、缺口和下一步动作。
- 输出明确 `real_llm_executed=false`, `database_connected=false`, `redis_connected=false`, `external_mcp_connected=false`, `migration_executed=false`, `business_data_written=false`, `audit_data_written=false`, `metrics_data_written=false`。
- 保持只读边界：不调用真实 LLM，不连接真实 PostgreSQL/Redis/MCP，不执行 Alembic migration，不读取或输出 secret 原文。
- 当前仍不宣称真实 LLM、PostgreSQL、Redis 或真实 MCP Server 生产验收完成。

## v4.4 Phase 24.2 MCP tool allowlist runtime guard（当前推进中）

- `MCP_TOOL_ALLOWLIST` 已进入 `Settings`、`.env.example`、`.env.production.example`、`ToolGateway`、`app.main` 真实 MCP 注册路径和 deployment guard。
- `ToolGateway` 在 MCP discovery 阶段过滤未列入 allowlist 的工具，并在 MCP call 阶段做二次拦截。
- `MCP_MODE=real` 的 production deployment guard 现在要求 `MCP_SERVER_COMMAND_ALLOWLIST` 与 `MCP_TOOL_ALLOWLIST` 均非空。
- 默认 `MCP_MODE=fake` 不变；未配置 `MCP_TOOL_ALLOWLIST` 时 fake/offline 与历史本地测试路径不受影响。
- 真实 MCP 工具调用仍必须经过 ToolGateway、PolicyEngine、审批链路和审计链路，不允许绕过。

## v4.4 Phase 24.3 Redis rate limit backend opt-in（当前推进中）

- `RATE_LIMIT_BACKEND` 已进入 `Settings`、`.env.example`、`.env.production.example`、`RateLimitMiddleware` 和 deployment guard。
- 默认 `RATE_LIMIT_BACKEND=memory`，保持原有离线/单实例路径不变。
- `RATE_LIMIT_BACKEND=redis` 时使用 Redis `INCR` + `EXPIRE` 做固定窗口计数；Redis disabled、NoopRedisClient 或 Redis 异常时回落 memory backend。
- deployment guard 校验 `RATE_LIMIT_BACKEND` 只能为 `memory/redis`；当选择 `redis` 时要求 `REDIS_ENABLED=true` 与 `REDIS_URL` 非空。
- Redis 连接成功日志不输出 `REDIS_URL` 原文。
- 当前仍不宣称真实 Redis 多实例限流生产验收完成；真实生产验收仍需受控 Redis smoke、故障恢复、断连降级和观测证据。

## v4.4 Phase 24.4 Real integration smoke plan/gate（当前推进中）

- 已新增只读 smoke plan 文档：`docs/real_integration_smoke_plan_v44.md`。
- 已新增只读 smoke plan 脚本：`scripts/real_integration_smoke_plan.py`。
- 已新增测试：`tests/test_real_integration_smoke_plan_v443.py`。
- 已新增只读 env profile 文档：`docs/real_integration_env_profile_v44.md`。
- 已新增只读 env profile 脚本：`scripts/real_integration_env_profile.py`。
- 已新增测试：`tests/test_real_integration_env_profile_v444.py`。
- 默认输出目录：`docs/reports/real_integration_smoke_plan/`。
- env profile 默认输出目录：`docs/reports/real_integration_env_profile/`。
- 覆盖 `real_llm`、`postgres`、`redis`、`external_mcp` 四个域的 opt-in 条件、env present、`REAL_LLM_API_KEY_ENV` 指向 env 的 present 布尔、计划 smoke 步骤、缺口和阻断项。
- env profile 只读解析 `.env.example` 与 `.env.production.example` 的键名和占位状态；生产模板已补齐 v4.4 real LLM smoke/preflight 相关键，但默认仍关闭，当前环境未 opt-in 时必须保持 `skipped`，不得伪造成可执行。
- 当前入口只做计划门禁，不提供执行真实连接的 CLI 参数；所有执行标志保持 false。
- 默认无 opt-in 时 `status=skipped`；四域条件齐备但未执行真实连接时 `status=partial` 且 `combined_staging_gate=Manual-Review`。
- 保持只读边界：不调用真实 LLM，不连接真实 PostgreSQL/Redis/MCP，不执行 Alembic migration，不写业务/审计/指标数据，不读取或输出 secret 原文。

## v4.4 Phase 24.5 Combined real integration staging gate（当前推进中）

- 已新增只读组合门禁文档：`docs/real_integration_staging_gate_v44.md`。
- 已新增只读组合门禁脚本：`scripts/real_integration_staging_gate.py`。
- 已新增测试：`tests/test_real_integration_staging_gate_v442.py`。
- 默认输出目录：`docs/reports/real_integration_staging_gate/`。
- 组合消费 `real_integration_readiness`、`real_llm_provider_acceptance_gate`、`external_mcp_acceptance_gate`、`store_redis_readiness_drill` 四类 JSON 证据，只读取结构化字段，不读取 Markdown 正文。
- 缺少证据或上游证据为 `skipped/failed` 时组合 gate 保持 `skipped`；发现 secret-like 内容、异常执行 flag 或上游 `blocked` 时组合 gate 必须 `blocked`，不得伪造成 `success`。
- 输出明确 `real_llm_executed=false`, `database_connected=false`, `redis_connected=false`, `external_mcp_connected=false`, `migration_executed=false`, `business_data_written=false`, `audit_data_written=false`, `metrics_data_written=false`, `secret_plaintext_output=false`。
- `combined_staging_gate=Manual-Review` 只表示进入人工复核，不代表自动上线；`public_production_direct_launch` 始终为 `No-Go`。
- 保持只读边界：不调用真实 LLM，不连接真实 PostgreSQL/Redis/MCP，不执行 Alembic migration，不写业务/审计/指标数据，不读取或输出 secret 原文。

## v3.7 Phase 17.4 Store and Redis production readiness drill（当前已完成）

- 交付物：`docs/store_redis_readiness_drill_v37.md`, `scripts/store_redis_readiness_drill.py`, `tests/test_store_redis_readiness_drill_v374.py`.
- 默认输出目录：`docs/reports/store_redis_readiness_drill/`.
- 覆盖 PostgreSQL Store opt-in、Store Factory、SQLite fallback、Alembic migration precheck、Redis opt-in、NoopRedisClient fallback、进程内限流边界、deployment guard、审计/指标 store 边界和 compose readiness。
- 输出明确 `database_connected=false`, `redis_connected=false`, `migration_executed=false`, `business_data_written=false`, `audit_data_written=false`, `metrics_data_written=false`.
- 保持只读边界：不连接真实 PostgreSQL，不连接真实 Redis，不执行 Alembic migration，不写业务/审计/指标数据，不读取或输出 `DATABASE_URL`、`REDIS_URL`、`JWT_SECRET` 等 secret 原文。
- 当前仍不宣称 PostgreSQL、Redis 或多实例限流生产验收完成。
- Phase 17.5 与 v3.7.0 release prep 已完成；tag/Release 待用户单独确认。

## v3.7 Phase 17.5 Business system integration safety checklist（当前已完成）

- 交付物：`docs/business_system_integration_safety_checklist_v37.md`, `scripts/business_system_integration_safety_checklist.py`, `tests/test_business_system_integration_safety_checklist_v375.py`.
- 默认输出目录：`docs/reports/business_system_integration_safety/`.
- 覆盖业务系统 opt-in、secret target、ToolGateway/PolicyEngine/OperationWhitelist、allowlist 与超时、写入边界、审批恢复、审计证据、request/prompt safety、回滚与失败恢复证据。
- 输出明确 `business_system_connected=false`, `business_read_executed=false`, `business_write_executed=false`, `business_data_written=false`, `approval_bypassed=false`, `audit_bypassed=false`.
- 保持只读边界：不连接真实业务系统，不执行真实读写，不创建/更新/删除业务数据，不绕过 ToolGateway、PolicyEngine、审批链路或审计链路，不读取或输出 token/API key/client_secret/业务系统 URL 原文。
- 当前仍不宣称真实业务系统生产集成验收完成。
- 建议下一阶段：Phase 17.6 v3.7 release prep。

## v3.7.0 release prep（当前已完成）

- 版本已同步到 `3.7.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、v3.7 脚本 version markers、相关测试断言。
- 已新增 `RELEASE_NOTES_v3.7.0.md`。
- 已新增 `docs/release_review_v3.7_external_integration_real_provider_acceptance.md`。
- Phase 17.1~17.5 纳入 v3.7.0 release prep 范围。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；默认不连接真实外部 MCP、真实业务系统、真实 PostgreSQL、真实 Redis 或真实 IdP。
- 不宣称公网生产可直接上线，不宣称真实 LLM/MCP/PostgreSQL/Redis/业务系统生产验收完成，不宣称生产级 SSO/OIDC、多租户或复杂 BI 全量完成。

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
| **v2.4.0** | Operator Console Pilot | 试点级运营台闭环（Dashboard/Tasks/Approvals/Trace/Audit/Metrics/RBAC/Tools/NL2SQL + Docker 演示脚本）；默认离线可跑；638+ tests |
| **v2.5.0** | Real LLM Optional Acceptance Pack | Phase 5.1 provider preflight / Phase 5.2 opt-in real LLM smoke / Phase 5.3 token/cost/budget/cache/fallback 验收 / Phase 5.4 LLMJudge opt-in smoke / Phase 5.5 文档收口与 release prep；默认 fake/offline，默认测试不调用真实 LLM |
| **v2.6.0** | Phase 6.0 Engineering Readiness | 部署门禁（deployment guard）/ 生产模板（.env.production.example + compose override）/ prod 脚本 / CI 工程化增强；定位企业内网试点准生产可投入使用；默认离线路径不变 |
| **v2.7.0** | Production Security Baseline | Phase 7.1 CORS + 安全响应头 / Phase 7.2 request size limit + rate limit + basic abuse guard / Phase 7.3 结构化日志与脱敏 / Phase 7.4 审计留存与 JSONL 导出边界 / Phase 7.5 OIDC/SSO 最小接入骨架与配置预检；默认 fake/offline，默认测试不调用真实 LLM |
| **v2.8.0** | Controlled Real LLM Pilot | `/llm/preflight` 状态观测 + 前端 `/llm` 页面 / acceptance_summary 统一字段 / budget-cache-fallback 行为收敛 / LLMJudge opt-in 收敛 / 审计日志指标联动；默认 fake/offline，默认 pytest/CI 不调用真实 LLM |
| **v2.9.0** | Real LLM Controlled Pilot Evidence | Phase 9.1~9.4：试点报告 schema/writer、opt-in smoke 自动生成脱敏报告、NL2SQL/Judge/audit/metrics 证据串联、pilot evidence 只读 API 与前端只读入口；默认 fake/offline，默认 pytest/CI 不调用真实 LLM |

## Known Pitfalls

- **Multi-Agent 是规则型多角色编排**：Coordinator / Analyst / Executor / Reviewer 当前是规则驱动边界划分，不是完全自治多 Agent。不要在文档或代码中包装为“自治多 Agent”。
- **StdioMCPClient 已有 real protocol path**：支持 subprocess stdio + JSON-RPC initialize/tools/list/tools/call + lifecycle hardening；默认仍 `MCP_MODE=fake`，real 模式需显式配置 command/allowlist，且当前验收基于 fake stdio server fixture。
- **LLMJudgeProvider 已支持可选真实 provider 路径**：默认仍 fake/offline，默认测试不调用真实 LLM。不要在文档中宣称真实 LLM 生产验收已完成。
- **LangGraph runtime 边界**：v1.1 只有最小 StateGraph smoke；Phase 2 已实现默认关闭的 graph checkpoint / interrupt / resume adapter 最小闭环，仅支持 graph_runtime_enabled=true 下 graph_keyword 单工具 approval resume。不要声称已实现完整 LangGraph native Command resume。
- **不要在文档中夸大为“生产环境即插即用”**：本项目是 production-grade engineering prototype，不可直接用于生产部署。
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
- 不要在 v2.3 及以前宣称前端审批 UI 已完成
- v2.4 起允许实现试点级运营台/审批台，但不要宣称已完成生产级交付
- 不要重写 Harness Runtime
- 不要把规则型 Multi-Agent 包装成自治多 Agent
- 不要在默认配置下启用 auth_enabled / rbac_enabled / redis_enabled
- 不要删除 SQLite demo 数据和 SQLite store 实现
- 不要在 Phase 1 实现 LangGraph checkpoint / interrupt
- 不要宣称完整 LangGraph native Command resume、真实 MCP、真实 LLM 已完成
- 不要宣称生产级 SSO、多租户、复杂 BI、真实外部系统对接已完成

## v2.4.4 补充口径（试点前端收敛）

- 允许实现试点级前端运营台/审批台/观测台页面，但不得宣称生产级前端交付完成。
- RBAC 页面当前只做试点说明与状态展示，不实现生产登录系统，不实现 SSO。
- 默认演示路径仍保持 `AUTH_ENABLED=false`、`RBAC_ENABLED=false`，不得破坏离线演示能力。
- Docker 本地演示脚本仅用于本地试点验证，不作为生产部署方案。

## v2.4.0 release prep 口径

- v2.4.0 已完成试点级运营台闭环，不再使用“前端未实现”口径。
- 默认仍为离线演示路径，不依赖真实 LLM、真实外部 MCP。
- 前端 Tools 调用必须经过后端 ToolGateway / PolicyEngine / 审批链路，不能绕过。
- NL2SQL 默认 mock/fake，真实 LLM 仅可选配置，不进入默认验收。
- 不宣称生产级 SSO、多租户、复杂 BI、真实外部系统生产验收已完成。

## v2.5.0 release prep 口径

- v2.5.0 已完成真实 LLM 可选验收包（preflight / opt-in smoke / token/cost/budget/cache/fallback 验收 / LLMJudge opt-in smoke / 报告模板）。
- 默认路径仍为 fake/offline，默认测试不调用真实 LLM。
- 真实 LLM smoke 仅为 opt-in 验收，不等于生产验收完成。
- 不宣称真实外部 MCP Server、生产级 SSO、多租户、复杂 BI、完整 LangGraph native Command resume 已完成。
- 不宣称生产可直接上线。


## v2.6 / Phase 6.0 工程化口径

- 当前阶段定位：企业内网试点准生产可投入使用。
- 必须保留默认离线开发路径，不得强制依赖真实 LLM 或真实外部 MCP。
- 生产门禁通过 deployment guard 实现，配置错误返回结构化结果，不抛 500。
- 生产部署通过 `docker-compose.yml + docker-compose.prod.yml` override 与 `scripts/prod_*.ps1` 执行。
- 不宣称公网生产可直接上线。
- 未完成项仍包括：生产级 SSO/OIDC、多租户、复杂 BI、真实外部 MCP 生产验收。

## v3.1 产品化增强路线说明（历史）

- v3.1 采用分阶段推进，Phase 11.1~11.5 已完成（历史阶段）。
- 默认开发模板仍是 `docker-compose.yml`，用于本地离线开发与演示。
- 生产试点模板通过 `docker-compose.prod.yml` 叠加，不替换默认开发路径。
- 当前回归基线：831 passed, 4 skipped（默认 real_llm 用例 skip）。

## v2.7 安全基线推进口径（当前阶段）

- Phase 7.1（CORS + 安全响应头）已完成。
- Phase 7.2（request size limit + rate limit + basic abuse guard）已完成。
- guard 拦截响应（429/413/400/414）同样需覆盖安全响应头与允许来源 CORS 头。
- 当前限流为进程内内存版，适用于单实例内网试点；多实例生产需 Redis 或网关级限流。
- 当前阶段仍不等于完整公网生产安全基线，不宣称公网生产可直接上线。


## v2.7.0 release prep 口径

- v2.7.0 已完成 Production Security Baseline 阶段交付（Phase 7.1~7.5）。
- OIDC/SSO 当前仅为最小接入骨架与配置预检，默认关闭，不依赖真实外部 IdP。
- 默认 fake/offline，默认 pytest 不调用真实 LLM，真实 LLM 仍为 opt-in 验收。
- 审计导出默认脱敏，不导出 prompt 原文、密钥原文、连接串密码原文。
- 不宣称公网生产可直接上线，不宣称生产级 SSO/OIDC、多租户、复杂 BI 已完成。

## v2.9.0 Real LLM Controlled Pilot Evidence 口径（历史阶段）

- v2.9 阶段已完成受控试点证据交付，默认 fake/offline 路径不变。
- 默认 pytest/CI 不调用真实 LLM，真实 LLM 仅 opt-in 验收。
- `/llm/preflight` 与 LLM Pilot 页面用于配置预检和状态观测；`/llm/pilot/reports` 提供只读证据审查入口。
- 审计、日志、导出必须保持脱敏边界：不记录 prompt 原文、不输出密钥原文。
- 不宣称公网生产可直接上线，不宣称生产级 SSO/OIDC、多租户、复杂 BI 已完成。
- v2.8.0 GitHub Release 已由用户手动创建，tag 保持不变。
- v2.9.0 已完成 Phase 9.1~9.4 与 P0 cleanup，形成完整受控试点证据闭环。
- v2.9.0 GitHub Release 已由用户手动创建，tag 保持不变。
- 下一阶段进入 v3.0 生产落地最终阶段规划。
- v3.0 规划文档：`docs/v3_final_production_landing_plan.md`。
- v3.0 Phase 10.1 已建立执行记录模板：`docs/real_llm_pilot_execution_log_v30.md`（本轮待手动 opt-in）。
- v3.0 Phase 10.2 已建立部署演练与回滚记录：`docs/production_deployment_drill_v30.md`（本地/内网试点模拟）。
- v3.0 Phase 10.3 已建立运维监控与备份恢复演练记录：`docs/operations_monitoring_backup_drill_v30.md`（runbook 级演练，不引入复杂运维平台）。
- v3.0 Phase 10.4 已建立安全复核与 Go/No-Go 评审：`docs/security_go_no_go_review_v30.md`（企业内网试点/准生产演示 Go，公网生产直上 No-Go）。
- v3.0.0 GitHub Release 已由用户手动创建，tag 保持不变（历史发布事实）。
- v3.1.0 GitHub Release 已由用户手动创建，tag 保持不变。
- v3.1 发布材料归档：`RELEASE_NOTES_v3.1.0.md`、`docs/release_review_v3.1_productization_enhancement.md`、`docs/post_release_check_v3.1.0.md`。
- v3.1 规划文档：`docs/v3_1_productization_enhancement_plan.md`（v3.1.0 发布后，main 可继续文档收口演进）。
- v3.2 规划文档：`docs/v3_2_acceptance_observability_plan.md`（当前进入 v3.2.0 release prep，不打 tag、不创建 Release）。
- v3.2 Phase 12.1 已新增 Acceptance Snapshot：
  - `scripts/acceptance_snapshot.py`
  - `docs/acceptance_snapshot_runbook_v32.md`
  - 默认输出目录：`docs/reports/acceptance_snapshots/`
  - 默认 fake/offline，不触发真实 LLM；服务未启动时在线检查标记 skipped
- v3.1 Phase 11.1 已完成离线演示 seed 与 E2E 脚本：`scripts/demo_seed_data.py`、`scripts/demo_e2e.ps1`、`docs/demo_e2e_runbook_v31.md`。
- v3.1 Phase 11.2 已完成只读运营总览：后端 `GET /operations/summary` + 前端 `/operations`（只读、脱敏、不触发真实 LLM）。
- v3.1 Phase 11.3 已新增执行记录：`docs/real_llm_pilot_execution_log_v31.md`（本轮 opt-in 变量缺失，status=skipped，未执行真实外网 LLM）。
- v3.1 Phase 11.4 已新增 OIDC 演练文档：`docs/oidc_minimal_idp_drill_v31.md`（最小真实 IdP 配置演练，不等于生产级 SSO/OIDC 完成）。
- v3.1 Phase 11.5 已新增运维文档：`docs/operations_troubleshooting_index_v31.md`、`docs/backup_restore_checklist_v31.md`（文档化排障与备份恢复，不删除用户数据）。
- v3.1 发布后边界：不移动/删除/重建既有 tag；不宣称公网生产可直接上线、不宣称真实 LLM 生产验收已完成、不宣称生产级 SSO/OIDC/多租户/复杂 BI 全量完成；后续建议进入 v3.2 或下一阶段路线规划。


- v3.2 Phase 12.3 added Demo artifact bundle:
  - `scripts/demo_e2e.ps1` (supports `-ArtifactDir`, default `docs/reports/demo_artifacts/`)
  - `scripts/demo_artifact_bundle.py`
  - `docs/demo_artifact_bundle_runbook_v32.md`
  - artifact includes seed/online smoke/operations summary (when available)/pilot report index/acceptance snapshot
  - default fake/offline; when service is unavailable online smoke is skipped without false success
- v3.2 Phase 12.2 read-only operations observability polish complete:
  - frontend `/operations` enhanced for acceptance readability, empty/error/skipped state clarity, and long-path wrapping.
  - backend `/operations/summary` now includes read-only observability metadata:
    - `acceptance_snapshot_runbook_path`
    - `demo_artifact_runbook_path`
    - `artifact_default_dir`
    - `snapshot_default_dir`
    - `last_known_report_counts`
  - no write/delete action added, no real LLM trigger, no secret exposure.
- v3.2 Phase 12.4 added Failure Diagnostics Pack:
  - runbook: `docs/failure_diagnostics_pack_v32.md`
  - script: `scripts/failure_diagnostics.py`
  - output: JSON + Markdown, default `docs/reports/failure_diagnostics/`
  - scenarios include compose/deployment guard/OIDC/audit export/demo_e2e skipped/acceptance snapshot skipped/pilot reports empty/real LLM opt-in skipped
  - read-only only, no write/delete operation, no real external LLM execution
- v3.2 Phase 12.5 optional real LLM evidence retry:
  - execution log: `docs/real_llm_optional_retry_log_v32.md`
  - current round recorded `status=skipped` when required opt-in env is incomplete
  - no fake success report; no real external LLM execution without explicit opt-in
- v3.2.0 release prep materials:
  - `RELEASE_NOTES_v3.2.0.md`
  - `docs/release_review_v3.2_acceptance_observability.md`
  - main 超前 `v3.1.0` tag 属于 v3.2.0 prep（历史阶段描述）
- v3.2.0 GitHub Release 已由用户手动创建，`v3.2.0` tag 保持不变。
- 后续建议进入 v3.3 或下一阶段路线规划；继续保持边界：不宣称公网直上、不宣称真实 LLM 生产验收完成、不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- v3.3 规划文档已开启：`docs/v3_3_operational_automation_governance_plan.md`
  - 聚焦 v3.2 既有快照/产物/诊断/运营总览能力的自动化与治理流程沉淀
  - 本轮仅规划，不改业务逻辑，不改版本号，不打 tag，不创建 Release
- v3.3 Phase 13.1 已完成（Report index & retention）：
  - `scripts/report_index.py`
  - `tests/test_report_index_v331.py`
  - `docs/report_index_retention_runbook_v33.md`
  - 默认输出目录：`docs/reports/report_index/`
  - 只读边界：仅列出 stale candidates，不删除文件

- v3.3 Phase 13.2 已完成（Config drift checklist）：
  - `scripts/config_drift_check.py`
  - `tests/test_config_drift_v332.py`
  - `docs/config_drift_checklist_v33.md`
  - 默认输出目录：`docs/reports/config_drift/`
  - 只读边界：仅检查模板键漂移与告警，不修改 `.env`，不输出真实密钥值

- v3.3 Phase 13.3 已完成（Governance policy summary）：
  - `scripts/governance_policy_summary.py`
  - `tests/test_governance_policy_summary_v333.py`
  - `docs/governance_policy_summary_v33.md`
  - 默认输出目录：`docs/reports/governance_policy/`
  - 只读治理摘要：不写业务数据、不读取真实密钥、不执行真实外网 LLM

- v3.3 Phase 13.4 已完成（Operations automation script polish）：
  - `docs/operations_automation_scripts_v33.md`
  - `tests/test_operations_automation_scripts_v334.py`
  - 已统一 acceptance/demo artifact/failure diagnostics/report index/config drift/governance 脚本 summary 元字段
  - 保持只读边界：不删除用户数据、不自动清理报告、不修改 `.env`、不读取/输出真实 secret、不执行真实外网 LLM

## v3.3 Phase 13.5 Optional live drill window

- Deliverables: `docs/live_drill_window_v33.md`, `scripts/live_drill_window.py`, `tests/test_live_drill_window_v335.py`.
- Script output default: `docs/reports/live_drill_window/` (JSON + Markdown).
- Read-only boundary: no business-data writes, no `.env` mutation, no user-data deletion, no report auto-cleanup, no real secret value output, no real external LLM execution by default.
- Status vocabulary: `success / skipped / blocked / partial / failed`; `skipped` must include missing condition list.

## v3.3.0 release prep (current)

- Version synchronized to `3.3.0` for release prep only.
- Added release-prep artifacts:
  - `RELEASE_NOTES_v3.3.0.md`
  - `docs/release_review_v3.3_operational_automation_governance.md`
- Phase 13.1~13.5 are included in v3.3.0 prep scope.
- Live drill boundary: read-only precheck; when required real LLM/OIDC conditions are missing, result must be `skipped`.
- Keep constraints: no real external LLM execution by default, no secret plaintext, no historical tag movement, no v3.3.0 tag/release creation in this round.

## v3.3.0 release-created closure (current)

- GitHub Release `v3.3.0` was manually created by user.
- Release title: `Project B v3.3.0 - Operational Automation & Governance`.
- Release notes source: `RELEASE_NOTES_v3.3.0.md`.
- Tag remains unchanged: `v3.3.0^{}` = `0399b84de5c2232a451d02ef37a8b181d0b01ebe`.
- Historical tags remain unchanged:
  - `v3.2.0^{}` = `3c12985d15062328efe5711ee939ca28ba4dbacf`
  - `v3.1.0^{}` = `4ffb8044ccc0f1fb62c570308c8c9c4c8c46a99a`
  - `v3.0.0^{}` = `fa5b07b3ffb373d2f1060f38b6ef0a4d31b5194d`
- No real external LLM executed in this closure round.
- Keep boundaries: default fake/offline, default pytest/CI no real LLM, no public production direct-launch claim, no claim of real-LLM production acceptance completion, no claim of production-grade SSO/OIDC or full multitenancy/complex BI completion.
- main ahead of tag belongs to post-release documentation closure.
- Next suggested direction: enter v3.4 or next-stage roadmap planning.

## v3.4 路线规划（历史）

- 规划文档：`docs/v3_4_pilot_hardening_operator_experience_plan.md`。
- v3.4 定位：Pilot Hardening & Operator Experience。
- 规划阶段约束：不改业务逻辑、不改版本号、不打 tag、不创建 Release。
- `v3.3.0` GitHub Release 已完成，`v3.3.0/v3.2.0/v3.1.0/v3.0.0` tags 保持不变。
- 保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，默认不执行真实外网 LLM，不输出真实 secret 原文。
- 不宣称公网生产直上，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 已完成，不宣称多租户/复杂 BI 全量完成。
- Phase 14.1~14.6 已完成并进入 v3.4.0 发布收口。

## v3.4 Phase 14.1 Operator workflow polish（已完成）

- 已新增操作员工作流文档：`docs/operator_workflow_polish_v34.md`。
- 已新增只读索引脚本：`scripts/operator_workflow_index.py`。
- 已新增测试：`tests/test_operator_workflow_index_v341.py`。
- 默认输出目录：`docs/reports/operator_workflow/`。
- 覆盖 `/operations`、acceptance snapshot、demo artifact bundle、failure diagnostics、report index、config drift、governance summary、live drill window。
- 每个入口必须说明使用时机、默认输出目录、是否只读、是否调用真实 LLM、失败或 skipped 状态解释。
- 保持只读边界：不删除数据、不自动清理报告、不修改 `.env`、不读取或输出真实 secret 原文、不执行真实外网 LLM。

## v3.4 Phase 14.2 Incident rehearsal pack（已完成）

- 已新增故障演练文档：`docs/incident_rehearsal_pack_v34.md`。
- 已新增只读演练脚本：`scripts/incident_rehearsal_pack.py`。
- 已新增测试：`tests/test_incident_rehearsal_pack_v342.py`。
- 默认输出目录：`docs/reports/incident_rehearsal/`。
- 覆盖 service unavailable、docker compose config failure、prod compose missing required env、deployment check ok=false、operations unavailable/empty、acceptance/demo skipped、failure diagnostics blocked、report index empty/stale、config drift warnings、governance/live drill skipped、OIDC secret env missing、real LLM opt-in missing/skipped。
- 状态词：`success / skipped / blocked / partial / failed`；缺少 opt-in 条件必须 `skipped`，不得伪造成成功。
- 保持只读边界：默认不启动服务、不修改环境变量或 `.env`、不读取或输出真实 secret 原文、不执行真实外网 LLM。

## v3.4 Phase 14.3 Evidence archive manifest（已完成）

- 已新增证据归档文档：`docs/evidence_archive_manifest_v34.md`。
- 已新增只读 manifest 脚本：`scripts/evidence_archive_manifest.py`。
- 已新增测试：`tests/test_evidence_archive_manifest_v343.py`。
- 默认输出目录：`docs/reports/evidence_archive/`。
- 纳入 acceptance/demo/failure/report index/config drift/governance/live drill/operator workflow/incident rehearsal/release review/post release handoff 证据类型。
- 只记录文件元数据，不读取报告内容，不删除文件，不自动执行 retention 清理，不读取或输出真实 secret 原文。
- 空目录或缺失目录必须记录为 `skipped` 或 `warning`，不得伪造成成功。

## v3.4 Phase 14.4 Optional integration readiness matrix（已完成）

- 已新增准备度矩阵文档：`docs/optional_integration_readiness_matrix_v34.md`。
- 已新增只读矩阵脚本：`scripts/optional_integration_readiness.py`。
- 已新增测试：`tests/test_optional_integration_readiness_v344.py`。
- 默认输出目录：`docs/reports/optional_integration_readiness/`。
- 覆盖 real LLM、OIDC、external MCP、Postgres、Redis、frontend build/network dependency、deployment guard、audit export/redaction readiness。
- 仅检查配置存在性与本地可验证条件；仅输出 env name 与 `present=true/false`，不输出真实 secret 值。
- 不调用真实外网 LLM，不连接真实外部 MCP；缺少 opt-in 条件必须 `skipped`。

## v3.4 Phase 14.5 Pilot handoff checklist polish（已完成）

- 已新增交接文档：`docs/pilot_handoff_checklist_v34.md`。
- 已新增只读生成脚本：`scripts/pilot_handoff_checklist.py`。
- 已新增测试：`tests/test_pilot_handoff_checklist_v345.py`。
- 默认输出目录：`docs/reports/pilot_handoff/`。
- 覆盖 admin/operator/viewer/auditor、RBAC 边界、OIDC 最小演练边界、real LLM opt-in skipped/ready 解释、incident rehearsal、evidence archive manifest、optional integration readiness、backup/restore/checklist、known limitations。
- Go/No-Go：企业内网试点可继续，公网直上 No-Go，真实生产验收需另行执行。
- 保持只读边界：不读取 secret 原文、不执行真实外网 LLM、不写业务数据。

## v3.4.0 release prep（历史）

- 版本已在 release prep 阶段同步到 `3.4.0`。
- 已新增 release-prep 产物：
  - `RELEASE_NOTES_v3.4.0.md`
  - `docs/release_review_v3.4_pilot_hardening_operator_experience.md`
- Phase 14.1~14.5 纳入 v3.4.0 prep 范围。
- 保持约束：默认不执行真实外网 LLM，不输出真实 secret 原文，不移动历史 tag，release prep 当轮不创建 v3.4.0 tag/Release。
- Go/No-Go：release prep 当轮结论为可以进入 v3.4.0 tag 前最终复核。

## v3.4.0 release-created closure（已完成）

- GitHub Release `v3.4.0` 已由用户手动创建。
- Release 标题：`Project B v3.4.0 - Pilot Hardening & Operator Experience`。
- Release notes 来源：`RELEASE_NOTES_v3.4.0.md`。
- tag 保持不变：`v3.4.0^{}` = `868dd76496a08821dbb0a133cb28d0a62a51a5d7`。
- 历史 tag 保持不变：
  - `v3.3.0^{}` = `0399b84de5c2232a451d02ef37a8b181d0b01ebe`
  - `v3.2.0^{}` = `3c12985d15062328efe5711ee939ca28ba4dbacf`
  - `v3.1.0^{}` = `4ffb8044ccc0f1fb62c570308c8c9c4c8c46a99a`
  - `v3.0.0^{}` = `fa5b07b3ffb373d2f1060f38b6ef0a4d31b5194d`
- release-created 文档收口未执行真实外网 LLM。
- 保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，不宣称公网生产直上，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 或多租户/复杂 BI 全量完成。
- main 超前 tag 属于发布后文档收口。
- 后续建议进入 v3.5 或下一阶段路线规划。

## v3.5.0 release-created closure（当前）

- 规划文档：`docs/v3_5_controlled_pilot_expansion_plan.md`。
- 生产级后续路线图：`docs/enterprise_production_landing_roadmap.md`。
- v3.5 定位：Controlled Pilot Expansion & Evidence Operations。
- GitHub Release `v3.5.0` 已创建。
- Release 标题：`Project B v3.5.0 - Controlled Pilot Expansion & Evidence Operations`。
- Release notes 来源：`RELEASE_NOTES_v3.5.0.md`。
- 发布后检查：`docs/post_release_check_v3.5.0.md`。
- 远端 tag `v3.5.0` 指向 commit `90cf1b3a325032b6d865c82d11035c27cfee3017`，历史 tag 保持不变。
- 由于本机 `github.com:443` Git HTTPS 不通，本轮通过 GitHub API 创建远端 annotated tag/ref 与 Release；未移动、删除或重建远端 tag。
- 保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，默认不执行真实外网 LLM，不输出真实 secret 原文。
- 不宣称公网生产直上，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 已完成，不宣称多租户/复杂 BI 全量完成。
- main 超前 `v3.5.0` tag 属于发布后文档收口。
- 后续建议进入 v3.6 Enterprise Identity & Tenant Boundary 或下一阶段路线规划。

## v3.5 Phase 15.1 Pilot evidence comparison snapshot（已完成）

- 已新增证据对比 runbook：`docs/pilot_evidence_comparison_v35.md`。
- 已新增只读对比脚本：`scripts/pilot_evidence_comparison.py`。
- 已新增测试：`tests/test_pilot_evidence_comparison_v351.py`。
- 默认输出目录：`docs/reports/pilot_evidence_comparison/`。
- 支持 baseline/current manifest JSON 或证据目录输入，仅读取元数据，不读取报告正文。
- 输出新增、减少、变化文件统计；缺失或空输入必须 `skipped` 并记录 `warnings`，不得伪造成成功。
- 保持只读边界：不删除、不移动、不修改输入证据，不自动执行 retention 清理，不读取或输出真实 secret 原文，不执行真实外网 LLM。

## v3.5 Phase 15.2 Operator drill scoring rubric（已完成）

- 已新增评分 runbook：`docs/operator_drill_scoring_rubric_v35.md`。
- 已新增只读评分脚本：`scripts/operator_drill_scoring.py`。
- 已新增测试：`tests/test_operator_drill_scoring_v352.py`。
- 默认输出目录：`docs/reports/operator_drill_scoring/`。
- 评分维度覆盖 availability、recoverability、evidence_integrity、configuration_readiness、permission_boundary、known_limitations。
- 输入来源包括 incident rehearsal、pilot handoff、optional integration readiness、evidence comparison 的 JSON 元数据。
- 缺失输入或来源报告 skipped 必须保留 skipped 语义，不得伪造成成功。
- 保持只读边界：不读取报告正文、不写业务数据、不自动改变 Go/No-Go 结论、不读取或输出真实 secret 原文、不执行真实外网 LLM。

## v3.5 Phase 15.3 Controlled integration dry-run checklist（已完成）

- 已新增受控集成 dry-run runbook：`docs/controlled_integration_dry_run_v35.md`。
- 已新增只读 dry-run 脚本：`scripts/controlled_integration_dry_run.py`。
- 已新增测试：`tests/test_controlled_integration_dry_run_v353.py`。
- 默认输出目录：`docs/reports/controlled_integration_dry_run/`。
- 覆盖 real LLM、OIDC、external MCP、Postgres、Redis、frontend build/network、deployment guard、audit export redaction。
- 支持 `--readiness-report` 串联 Phase 14.4 optional integration readiness JSON，只消费结构化元数据。
- 缺少 opt-in 条件必须 `skipped` 并记录 `missing_conditions`，不得伪造成 `ready/success`。
- 保持只读边界：不启动服务、不修改 `.env`、不连接真实外部 MCP、不调用真实外网 LLM、不读取或输出真实 secret 原文。
- 生产级路线图已新增：`docs/enterprise_production_landing_roadmap.md`；当前仍不宣称生产级全量完成。

## v3.5 Phase 15.4 Governance exception register（已完成）

- 已新增治理例外登记 runbook：`docs/governance_exception_register_v35.md`。
- 已新增只读治理例外登记脚本：`scripts/governance_exception_register.py`。
- 已新增测试：`tests/test_governance_exception_register_v354.py`。
- 默认输出目录：`docs/reports/governance_exceptions/`。
- 支持引用 config drift、governance policy summary、incident rehearsal、operator drill scoring 的 JSON 元数据。
- 例外字段覆盖风险描述、影响范围、责任人、到期时间、补偿控制、复核证据、状态和下一步动作。
- 不自动批准例外，不绕过 deployment guard、安全响应头、审计脱敏或审批链路。
- 保持只读边界：不记录真实 secret 原文、不执行真实外网 LLM。
- Phase 15.4 交付当轮不改版本号、不打 tag、不创建 Release；当前版本已完成 `v3.5.0` 发布。

## v3.5 Phase 15.5 Pilot closeout report pack（已完成）

- 已新增试点收口报告 runbook：`docs/pilot_closeout_report_pack_v35.md`。
- 已新增只读收口报告脚本：`scripts/pilot_closeout_report_pack.py`。
- 已新增测试：`tests/test_pilot_closeout_report_pack_v355.py`。
- 默认输出目录：`docs/reports/pilot_closeout/`。
- 支持汇总 pilot handoff、evidence archive、optional integration readiness、operator scoring、controlled integration dry-run、governance exception register 的 JSON 元数据。
- 报告包包含 executive summary、evidence summary、known limitations、Go/No-Go、next actions 和 boundary declarations。
- 对所有 `skipped/blocked/partial` 项保持原始解释，不做假通过。
- 保持只读边界：不读取报告正文、不写业务数据、不执行真实外网 LLM、不输出真实 secret 原文。
- 当前版本已完成 `v3.5.0` 发布，tag 与 Release 已创建。

## v3.5 Phase 15.6 release prep（已完成）

- 已同步版本到 `3.5.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、脚本 version markers、相关测试断言。
- 已新增 `RELEASE_NOTES_v3.5.0.md`。
- 已新增 `docs/release_review_v3.5_controlled_pilot_expansion.md`。
- Phase 15.1~15.5 纳入 v3.5.0 release prep 范围。
- `v3.5.0` tag 与 GitHub Release 已创建；历史 tag 未移动、未删除、未重建。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；不执行真实外网 LLM。
- 发布后收口文档：`docs/post_release_check_v3.5.0.md`。

## v3.6.0 release prep（当前）

- 规划文档：`docs/v3_6_enterprise_identity_tenant_boundary_plan.md`。
- v3.6 定位：Enterprise Identity & Tenant Boundary。
- 当前已进入 release prep，版本已同步为 `3.6.0`。
- release prep 阶段约束：不打 tag，不创建 Release，不移动历史 tag。
- `v3.5.0` GitHub Release 已创建，`v3.5.0/v3.4.0/v3.3.0/v3.2.0/v3.1.0/v3.0.0` tags 保持不变。
- 现有 OIDC 仍为最小配置预检，不执行真实 token exchange，不宣称生产级 SSO/OIDC 完成。
- 当前尚未实现 tenant/org/project/resource ownership 运行时 enforcement，不宣称多租户完成。
- 保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，默认不连接真实外部 IdP，不输出真实 secret 原文。
- Phase 16.1~16.6 已完成；建议下一阶段：v3.6.0 tag 前最终复核。

## v3.6 Phase 16.1 Identity and tenant boundary inventory（已完成）

- 已新增 runbook：`docs/identity_tenant_boundary_inventory_v36.md`。
- 已新增只读盘点脚本：`scripts/identity_tenant_boundary_inventory.py`。
- 已新增测试：`tests/test_identity_tenant_boundary_inventory_v361.py`。
- 默认输出目录：`docs/reports/identity_tenant_boundary/`。
- 盘点覆盖 `User`、`TokenPayload`、`UserRole`、JWT、`ROLE_HIERARCHY`、`ENDPOINT_PERMISSIONS`、OIDC 配置预检、审计文件和资源归属概念。
- 当前盘点结果预期为 `partial`：用户/JWT 尚无 tenant/org/project scope，尚无 tenant ownership 统一模型和运行时 enforcement，审计尚未定义 tenant scope。
- 保持只读边界：不读取 `.env` 或真实 secret 值，不连接真实 IdP，不执行 OIDC token exchange，不改 JWT payload，不新增 tenant enforcement，不写业务数据。
- 不宣称生产级 SSO/OIDC 或多租户完成。

## v3.6 Phase 16.2 Tenant ownership model draft（已完成）

- 已新增模型设计文档：`docs/tenant_ownership_model_v36.md`。
- 已新增 Pydantic 草案模型：`OrganizationScopeDraft`、`TenantScopeDraft`、`ProjectScopeDraft`、`PrincipalScopeDraft`、`RoleAssignmentDraft`、`ResourceScopeDraft`、`AuditScopeDraft`、`TenantOwnershipModelDraft`。
- 已新增测试：`tests/test_tenant_ownership_model_v362.py`。
- 已明确 `organization`、`tenant`、`project`、`principal`、`role_assignment`、`resource_scope`、`audit_scope` 概念边界。
- 已明确未来可进入 JWT 的 claim 草案：`organization_id`、`tenant_id`、`project_id`；当前不改 `TokenPayload`。
- 已明确服务端 store 字段、审计字段、跨租户拒绝规则和迁移兼容策略。
- 本阶段不迁移数据库、不改 user store、不改 JWT payload、不启用 tenant enforcement、不改变默认离线 demo。
- 不宣称生产级 SSO/OIDC 或多租户完成。

## v3.6 Phase 16.3 RBAC matrix hardening（已完成）

- 已新增 runbook：`docs/rbac_permission_matrix_v36.md`。
- 已新增只读矩阵导出脚本：`scripts/rbac_permission_matrix.py`。
- 已新增测试：`tests/test_rbac_permission_matrix_v363.py`。
- 默认输出目录：`docs/reports/rbac_permission_matrix/`。
- 矩阵覆盖 admin/operator/viewer/auditor 对 tasks、approvals、audit、metrics、tools、eval、memory、reflection、snapshot 的权限边界。
- 输出包含 role hierarchy、allowed roles、denied roles、401/403 拒绝证据、权限申请和定期复核流程。
- 保持只读边界：不新增生产登录系统，不绕过 `require_permission`，不改变默认 API token 要求，不默认启用 `AUTH_ENABLED` 或 `RBAC_ENABLED`。
- 不宣称权限治理已生产完成，不宣称生产级 SSO/OIDC 或多租户完成。

## v3.6 Phase 16.4 OIDC lifecycle drill plan（已完成）

- 已新增 runbook：`docs/oidc_lifecycle_drill_v36.md`。
- 已新增只读演练计划脚本：`scripts/oidc_lifecycle_drill.py`。
- 已新增测试：`tests/test_oidc_lifecycle_drill_v364.py`。
- 默认输出目录：`docs/reports/oidc_lifecycle_drill/`。
- 演练计划覆盖 OIDC 配置预检、token 生命周期、登出与会话失效、JWKS 轮换、client_secret 轮换和失败路径。
- 缺少真实 IdP opt-in 条件时记录为 `skipped`，不得伪造成 success。
- 所有 secret 只输出 env name 与 present 布尔状态。
- 本阶段默认不连接真实 IdP，不执行 OIDC token exchange，不修改 `.env`，不默认启用 `AUTH_ENABLED`、`RBAC_ENABLED`、`OIDC_ENABLED`。
- 不宣称生产级 SSO/OIDC 或多租户完成。

## v3.6 Phase 16.5 Cross-tenant audit and denial evidence（已完成）

- 已新增 runbook：`docs/cross_tenant_audit_evidence_v36.md`。
- 已新增只读证据模板脚本：`scripts/cross_tenant_audit_evidence.py`。
- 已新增测试：`tests/test_cross_tenant_audit_evidence_v365.py`。
- 默认输出目录：`docs/reports/cross_tenant_audit_evidence/`。
- 证据模板覆盖 allow、deny、audit record、export redaction、reviewer/owner evidence。
- 已明确未来 audit event 必需 scope 字段：`organization_id`、`tenant_id`、`project_id`、`resource_id`、`actor_principal_id`、`decision`、`denial_reason`。
- 支持引用 RBAC matrix、tenant model 文档和 audit export sample，仅消费元数据；发现 prompt/secret/token/连接串密码原文时输出 `blocked`，且不泄露原文。
- 保持只读边界：不修改 audit store schema，不生成伪造的跨租户通过证据，不启用 tenant enforcement，不改 JWT payload。
- 不宣称生产级 SSO/OIDC 或多租户完成。

## v3.6 Phase 16.6 release prep（已完成）

- 已同步版本到 `3.6.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、脚本 version markers、相关测试断言。
- 已新增 `RELEASE_NOTES_v3.6.0.md`。
- 已新增 `docs/release_review_v3.6_enterprise_identity_tenant_boundary.md`。
- Phase 16.1~16.5 纳入 v3.6.0 release prep 范围。
- 前端移除构建期 Google Fonts 依赖，默认离线 build 可通过。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；不执行真实外网 LLM。
- 不宣称公网生产可直接上线，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 或多租户完成。

## v3.7 路线规划已开启（当前）

- 规划文档：`docs/v3_7_external_integration_real_provider_acceptance_plan.md`。
- v3.7 定位：External Integration & Real Provider Acceptance。
- 当前先进入规划与只读基线阶段，版本保持 `3.6.0`。
- 本轮不打 tag、不创建 GitHub Release、不移动历史 tag。
- 由于当前环境 GitHub HTTPS 推送不可用，`v3.6.0` release prep 提交已在本地完成，远端同步需网络恢复后执行。
- Phase 17.1~17.5 与 v3.7.0 release prep 已完成；tag/Release 待用户单独确认。

## v3.7 Phase 17.1 External integration baseline inventory（已完成）

- 已新增 runbook：`docs/external_provider_acceptance_inventory_v37.md`。
- 已新增只读盘点脚本：`scripts/external_provider_acceptance_inventory.py`。
- 已新增测试：`tests/test_external_provider_acceptance_inventory_v371.py`。
- 默认输出目录：`docs/reports/external_provider_acceptance_inventory/`。
- 盘点覆盖 external MCP、real LLM provider、LLM judge、PostgreSQL、Redis、deployment guard、tool approval audit、frontend offline build。
- 输出明确 `read_only=true`、`real_llm_executed=false`、`external_mcp_connected=false`、`business_system_connected=false`。
- 仅输出 env name、present 布尔状态和本地文件存在性，不读取或输出真实 secret 原文。
- 不宣称真实 provider、真实外部 MCP 或真实业务系统生产验收完成。

## v3.7 Phase 17.2 External MCP acceptance gate（已完成）

- 已新增 runbook：`docs/external_mcp_acceptance_gate_v37.md`。
- 已新增只读门禁脚本：`scripts/external_mcp_acceptance_gate.py`。
- 已新增测试：`tests/test_external_mcp_acceptance_gate_v372.py`。
- 默认输出目录：`docs/reports/external_mcp_acceptance_gate/`。
- 门禁覆盖 real mode opt-in、command configured、command allowlist、tool allowlist、timeout config、lifecycle hardening、approval/audit boundary、fake fixture coverage。
- 输出明确 `external_mcp_connected=false`、`mcp_process_started=false`、`mcp_tools_list_executed=false`、`mcp_tools_call_executed=false`。
- 本阶段不启动 MCP subprocess，不执行真实 `tools/list` 或 `tools/call`，不宣称真实外部 MCP 生产验收完成。

## v3.7 Phase 17.3 Real LLM provider acceptance gate（已完成）

- 已新增 runbook：`docs/real_llm_provider_acceptance_gate_v37.md`。
- 已新增只读门禁脚本：`scripts/real_llm_provider_acceptance_gate.py`。
- 已新增测试：`tests/test_real_llm_provider_acceptance_gate_v373.py`。
- 默认输出目录：`docs/reports/real_llm_provider_acceptance_gate/`。
- 门禁覆盖 preflight config、network check gate、smoke opt-in、budget/cache/fallback、PII/prompt guardrails、report redaction、judge acceptance、evidence index。
- 输出明确 `real_llm_executed=false`、`provider_network_check_executed=false`、`pilot_report_content_read=false`。
- 可选索引 pilot report 目录时仅读取文件元数据，不读取报告正文。
- 本阶段不调用真实外网 LLM，不执行 provider network check，不宣称真实 LLM 生产验收完成。
## v3.8 Phase 18.1 SRE observability baseline（当前已完成）

- 已新增 SRE 观测基线 runbook：`docs/sre_observability_baseline_v38.md`。
- 已新增只读基线脚本：`scripts/sre_observability_baseline.py`。
- 已新增测试：`tests/test_sre_observability_baseline_v381.py`。
- 默认输出目录：`docs/reports/sre_observability_baseline/`。
- 覆盖 runtime metrics/cost API、runtime snapshot、operations summary、audit export、structured logging、failure diagnostics、backup/restore runbook、外部 APM、告警、容量、备份与 DR 缺口。
- 默认不启动服务，不访问在线 `/health`、`/metrics`、`/operations`、`/runtime/snapshot`，不连接真实 APM、日志平台、告警平台或值班系统。
- 默认不执行真实压测、备份恢复或灾备切换，不删除用户数据，不自动清理报告，不修改 `.env`。
- 缺少 SRE/APM/告警/容量/备份/DR opt-in 条件时必须记录为 `skipped`，不得伪造成 `success`。
- 保持边界：不读取或输出真实 secret 原文，不把本地 metrics store、只读脚本或 runbook 宣称为企业级 SRE 验收完成。
## v3.8 Phase 18.2 SLO/SLI and alerting runbook pack（当前已完成）

- 已新增 SLO/告警 runbook：`docs/slo_alerting_runbook_pack_v38.md`。
- 已新增只读脚本：`scripts/slo_alerting_runbook_pack.py`。
- 已新增测试：`tests/test_slo_alerting_runbook_pack_v382.py`。
- 默认输出目录：`docs/reports/slo_alerting_runbook/`。
- 覆盖 SLO/SLI 指标来源、SLO 目标配置、structured logging 告警上下文、告警分级与路由、on-call 升级、alert dry-run 证据、incident runbook 串联和回归测试覆盖。
- 默认不启动服务，不访问在线端点，不连接真实 APM、日志平台、告警平台或值班系统。
- 默认不发送真实告警，不通知真实 on-call，不调用真实 webhook，不执行真实 incident 升级。
- 缺少 SLO/告警/on-call/dry-run opt-in 或演练证据时必须记录为 `skipped`，不得伪造成 `success`。
- 保持边界：不读取或输出真实 secret 原文，不把 runbook、placeholder env 或本地 metrics store 宣称为企业级 SLO/告警验收完成。
## v3.8 Phase 18.3 Backup/restore and DR drill evidence pack（当前已完成）

- 已新增备份恢复与 DR 证据 runbook：`docs/backup_restore_dr_evidence_pack_v38.md`。
- 已新增只读脚本：`scripts/backup_restore_dr_evidence_pack.py`。
- 已新增测试：`tests/test_backup_restore_dr_evidence_pack_v383.py`。
- 默认输出目录：`docs/reports/backup_restore_dr_evidence/`。
- 覆盖备份范围、部署与迁移边界、RTO/RPO 配置、备份演练证据、恢复 dry-run 证据、DR failover 证据、runbook 串联和回归测试覆盖。
- 默认不启动服务，不连接真实 PostgreSQL、Redis、对象存储、IdP、LLM provider 或外部 MCP。
- 默认不执行真实备份、恢复、灾备切换或 Alembic migration，不写业务/审计/指标数据。
- 缺少备份/恢复/DR opt-in 或演练证据时必须记录为 `skipped`，不得伪造成 `success`。
- 保持边界：不读取或输出真实 secret 原文，不把 runbook、placeholder env 或本地 SQLite 文件宣称为 RTO/RPO 或 DR 生产验收完成。
## v3.8 Phase 18.4 Capacity and load-test readiness plan（当前已完成）

- 已新增容量与压测准备 runbook：`docs/capacity_load_test_readiness_plan_v38.md`。
- 已新增只读脚本：`scripts/capacity_load_test_readiness_plan.py`。
- 已新增测试：`tests/test_capacity_load_test_readiness_plan_v384.py`。
- 默认输出目录：`docs/reports/capacity_load_test_readiness/`。
- 覆盖关键 API 入口、流量模型目标、request guard、容量测试可观测性、load-test dry-run 证据、soak test 证据、runbook 串联和回归测试覆盖。
- 默认不启动服务，不访问在线端点，不执行真实压测、soak test、并发请求或容量探测。
- 默认不连接真实 PostgreSQL、Redis、APM、日志平台、告警平台、IdP、LLM provider、外部 MCP 或业务系统。
- 缺少容量/压测/soak opt-in 或报告证据时必须记录为 `skipped`，不得伪造成 `success`。
- 保持边界：不读取或输出真实 secret 原文，不把 runbook、placeholder env 或本地测试通过宣称为生产容量上限验收完成。
## v3.8.0 release prep（当前已完成）

- 版本已同步到 `3.8.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、v3.8 脚本 version markers、相关测试断言。
- 已新增 `RELEASE_NOTES_v3.8.0.md`。
- 已新增 `docs/release_review_v3.8_sre_observability_dr.md`。
- Phase 18.1~18.4 纳入 v3.8.0 release prep 范围。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；默认不连接真实 APM、日志、告警、对象存储、PostgreSQL、Redis、IdP、外部 MCP 或业务系统。
- 不宣称公网生产可直接上线，不宣称企业级 SRE、RTO/RPO、DR、容量上限、真实 LLM 生产验收、生产级 SSO/OIDC 或多租户完成。
## v3.9 Compliance Security Hardening 路线规划（当前）

- 规划文档：`docs/v3_9_compliance_security_hardening_plan.md`。
- v3.9 定位：Compliance Security Hardening。
- 当前先进入只读基线与 runbook 阶段，版本保持 `3.8.0`。
- 本轮不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- 默认不连接真实 IdP、APM、日志平台、告警平台、对象存储、PostgreSQL、Redis、外部 MCP 或业务系统。
- 默认不执行真实安全扫描、真实密钥轮换、真实权限变更、真实审计导出、真实发布、真实回滚或真实外部系统调用。
- 不宣称公网生产可直接上线，不宣称企业级合规、安全治理、发布门禁或密钥治理完成。

## v3.9 Phase 19.1 Compliance security baseline inventory（当前已完成）

- 已新增合规安全基线 runbook：`docs/compliance_security_baseline_v39.md`。
- 已新增只读脚本：`scripts/compliance_security_baseline.py`。
- 已新增测试：`tests/test_compliance_security_baseline_v391.py`。
- 默认输出目录：`docs/reports/compliance_security_baseline/`。
- 覆盖 deployment guard、安全响应头、request guard、结构化日志脱敏、审计留存与导出、RBAC、OIDC、prompt injection、PII guard、跨租户审计和 release review 证据缺口。
- 默认不启动服务，不访问在线端点，不连接真实外部系统。
- 默认不执行真实安全扫描、审计导出、密钥轮换、权限变更、发布或回滚。
- 缺少正式合规签核、审计复核、发布门禁复核或密钥轮换演练证据时必须记录为 `skipped`，不得伪造成 `success`。
- 保持边界：不读取或输出真实 secret 原文，不把配置模板、只读脚本或 runbook 宣称为企业级合规、安全治理或发布门禁验收完成。
## v3.9 Phase 19.2 Secret rotation and leakage response pack（当前已完成）

- 已新增密钥轮换与泄漏响应 runbook：`docs/secret_rotation_leakage_response_pack_v39.md`。
- 已新增只读脚本：`scripts/secret_rotation_leakage_response_pack.py`。
- 已新增测试：`tests/test_secret_rotation_leakage_response_pack_v392.py`。
- 默认输出目录：`docs/reports/secret_rotation_leakage_response/`。
- 覆盖 JWT/OIDC/数据库/Redis/LLM/MCP/业务系统/告警 webhook 等 secret surface、脱敏审计边界、身份密钥生命周期、外部集成密钥边界、治理例外串联、轮换/泄漏响应/撤销恢复演练证据缺口。
- 默认不读取 `.env` 或真实 secret 值，不连接真实 KMS、Vault、云平台、IdP、LLM provider、外部 MCP、数据库、Redis、告警平台或业务系统。
- 默认不执行真实密钥创建、轮换、撤销、禁用、泄漏扫描或告警通知。
- 缺少轮换、泄漏响应或撤销恢复演练证据时必须记录为 `skipped`，不得伪造成 `success`。
- 保持边界：不读取或输出真实 secret 原文，不把配置模板、env name、只读脚本或 runbook 宣称为企业级密钥治理完成。
## v3.9 Phase 19.3 Release gate and rollback governance pack（当前已完成）

- 已新增发布门禁与回滚治理 runbook：`docs/release_gate_rollback_governance_pack_v39.md`。
- 已新增只读脚本：`scripts/release_gate_rollback_governance_pack.py`。
- 已新增测试：`tests/test_release_gate_rollback_governance_pack_v393.py`。
- 默认输出目录：`docs/reports/release_gate_rollback_governance/`。
- 覆盖 deployment guard、compose、Alembic、release notes、release review、变更审批、发布签核、回滚演练、治理例外和安全合规串联证据缺口。
- 默认不启动服务，不访问在线端点，不执行 git tag、GitHub Release、部署、迁移、回滚、数据恢复或外部系统调用。
- 缺少变更审批、发布签核或回滚演练证据时必须记录为 `skipped`，不得伪造成 `success`。
- 保持边界：不读取或输出真实 secret 原文，不把 release notes、release review、runbook 或配置模板宣称为生产发布门禁或回滚验收完成。
## v3.9 Phase 19.4 Security regression and compliance evidence pack（当前已完成）

- 已新增安全回归与合规证据 runbook：`docs/security_regression_compliance_evidence_pack_v39.md`。
- 已新增只读脚本：`scripts/security_regression_compliance_evidence_pack.py`。
- 已新增测试：`tests/test_security_regression_compliance_evidence_pack_v394.py`。
- 默认输出目录：`docs/reports/security_regression_compliance_evidence/`。
- 覆盖 prompt injection、PII 泄漏、SQL guard、边界防护、身份/RBAC、跨租户拒绝、审计导出脱敏、发布门禁和合规证据串联缺口。
- 默认不启动服务，不访问在线端点，不执行真实 SAST、DAST、依赖扫描、红队测试、外部审计或外部系统调用。
- 缺少外部安全扫描、正式安全签核或合规证据复核时必须记录为 `skipped`，不得伪造成 `success`。
- 保持边界：不读取或输出真实 secret 原文，不把本地测试存在性、runbook 或只读证据索引宣称为企业级安全合规验收完成。
## v3.9.0 release prep（当前已完成）

- 版本已同步到 `3.9.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、v3.9 脚本 version markers、相关测试断言。
- 已新增 `RELEASE_NOTES_v3.9.0.md`。
- 已新增 `docs/release_review_v3.9_compliance_security_hardening.md`。
- Phase 19.1~19.4 纳入 v3.9.0 release prep 范围。
- 本轮验证：v3.9 聚焦验证 56 passed；v3.9 安全/合规回归 161 passed；全量 `python -m pytest -q` 为 920 passed, 4 skipped, 2 warnings；`git diff --check` 仅 CRLF 提示。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；默认不连接真实外部系统。
- 不宣称公网生产可直接上线，不宣称企业级合规、安全治理、密钥治理、发布门禁、回滚验收、真实 LLM 生产验收、生产级 SSO/OIDC 或多租户完成。

## v4.0 Phase 20.1 Production launch readiness evidence review pack（当前已完成）

- 规划文档：`docs/v4_0_production_launch_readiness_plan.md`。
- 已新增 runbook：`docs/production_launch_readiness_review_v40.md`。
- 已新增只读脚本：`scripts/production_launch_readiness_review.py`。
- 已新增测试：`tests/test_production_launch_readiness_review_v401.py`。
- 默认输出目录：`docs/reports/production_launch_readiness/`。
- 覆盖 v3.5~v3.9 试点收口、证据归档、真实 provider 验收、SRE/DR、容量、安全合规、发布门禁和回滚治理证据入口。
- 默认状态为 `partial`，Go/No-Go 建议为 `Manual-Review`，公网生产直上为 `No-Go`；不把缺失真实验收证据伪造成 `success`。
- 已根据子 agent 审查收紧上游 `blocked/failed`、输入不足 `skipped`、secret-like JSON 键值脱敏和 blocked 状态下 `controlled_internal_pilot=No-Go` 语义。
- 已根据子 agent 审查补强 `external_system_connected` 边界违规识别。
- 验证通过：v4.0 Phase 20.1 单测 7 passed；v4.0 + v3.9 关联测试随 Phase 20.2 更新为 34 passed, 1 warning；`git diff --check` 仅 CRLF 提示。
- 保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，不连接真实外部系统，不读取或输出真实 secret 原文，不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、审计导出、密钥轮换或权限变更。
- 本阶段不改版本号，不打 tag，不创建 GitHub Release，不宣称生产上线批准完成。

## v4.0 Phase 20.2 Launch blocker register（当前已完成）

- 已新增 runbook：`docs/launch_blocker_register_v40.md`。
- 已新增只读脚本：`scripts/launch_blocker_register.py`。
- 已新增测试：`tests/test_launch_blocker_register_v402.py`。
- 默认输出目录：`docs/reports/launch_blockers/`。
- 将 Phase 20.1 的 production blockers 和 missing conditions 整理为人工跟踪台账，字段覆盖 blocker id、来源、风险描述、影响范围、责任人、到期时间、补偿控制、关闭证据、状态、审批状态和下一步动作。
- 默认无上游输入或上游 `skipped` 时输出 `skipped`；存在待关闭 blocker 时输出 `partial`；上游 `blocked/failed`、secret-like 输入、自动批准/关闭标记或边界违规时输出 `blocked`。
- 保持 `auto_approved=false`、`auto_closed=false`；不自动批准上线，不自动关闭阻断项，不宣称生产 Go。
- 已根据子 agent 审查补强上游 `skipped` 保留、`auto_approved/auto_closed` 阻断和 success 语义文档。
- 验证通过：v4.0 Phase 20.1/20.2 + v3.9 关键安全合规关联测试 34 passed, 1 warning；`git diff --check` 仅 CRLF 提示。
- 保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，不连接真实外部系统，不读取或输出真实 secret 原文，不执行真实生产操作。

## v4.0 Phase 20.3 Production runbook finalization（当前已完成）

- 已新增 runbook：`docs/production_runbook_finalization_v40.md`。
- 已新增只读脚本：`scripts/production_runbook_finalization.py`。
- 已新增测试：`tests/test_production_runbook_finalization_v403.py`。
- 默认输出目录：`docs/reports/production_runbook_finalization/`。
- 汇总部署、回滚、incident、DR、密钥轮换、审计导出、SLO/告警、容量、Launch Readiness 和 blocker register 的本地 runbook 入口。
- 默认仅检查本地文件存在性和可选上游 JSON 结构化字段，不读取 Markdown 报告正文。
- 输出明确 `deployment_executed=false`、`rollback_executed=false`、`alert_sent=false`、`oncall_notified=false`、`auto_approved=false`、`auto_closed=false`。
- 保持边界：默认 fake/offline，不连接真实外部系统，不读取或输出真实 secret 原文，不执行真实生产操作，不把 runbook 入口存在性伪造成生产 Go。
- 已根据子 agent 审查补强：缺少上游 Phase 20.1/20.2 JSON 时输出 `skipped`，透传 blocker 计数与上游 Go/No-Go，audit log/export 验证入口纳入必需项。
- 验证通过：v4.0 Phase 20.1/20.2/20.3 + v3.9 关键安全合规关联测试 39 passed；`git diff --check` 仅 CRLF 提示。

## v4.1 Phase 21.1 Launch blocker closure workflow（当前已完成）

- 交付物：`docs/v4_1_evidence_execution_closure_plan.md`, `docs/launch_blocker_closure_workflow_v41.md`, `scripts/launch_blocker_closure_workflow.py`, `tests/test_launch_blocker_closure_workflow_v411.py`。
- 默认输出目录：`docs/reports/launch_blocker_closure/`。
- 输入为 v4.0 Launch Blocker Register JSON 与可选脱敏 closure evidence JSON。
- 仅判断 blocker 是否具备进入人工复核的 owner、due_at、补偿控制、证据引用、reviewer 与审批状态。
- 即使所有 blocker 证据齐全，也保持整体 `partial` + `Manual-Review`，不自动产出 `success`，不宣称生产 Go。
- 输出明确 `auto_approved=false`, `auto_closed=false`, `production_direct_launch=No-Go`, `real_llm_executed=false`, `external_mcp_connected=false`, `external_system_connected=false`。
- 保持只读边界：不读取 Markdown 正文，不修改上游报告，不修改 `.env`，不读取或输出真实 secret 原文，不连接真实外部系统，不执行真实部署/迁移/发布/回滚/压测/备份恢复/DR failover/安全扫描/审计导出/密钥轮换/权限变更。
- 当前仍不宣称上线 blocker 已关闭，不宣称生产发布批准完成。
- 验证通过：v4.1 Phase 21.1 单测 8 passed。

## v4.1 Phase 21.2 Closure evidence index（当前已完成）

- 交付物：`docs/closure_evidence_index_v41.md`, `scripts/closure_evidence_index.py`, `tests/test_closure_evidence_index_v412.py`。
- 默认输入目录：`docs/reports/launch_blocker_closure/`。
- 默认输出目录：`docs/reports/closure_evidence_index/`。
- 仅索引 closure workflow JSON 的结构化元数据，汇总 report count、latest report、closure item totals 与状态分布。
- 不读取 Markdown 报告正文，不展开证据报告内容，不修改、不移动、不删除输入证据，不自动执行 retention 清理。
- 检测到 secret-like 输入、非只读报告、自动审批/自动关闭标记或上游 blocked/failed 时输出 `blocked`。
- 输出明确 `production_direct_launch=No-Go`, `auto_approved=false`, `auto_closed=false`, `real_llm_executed=false`, `external_mcp_connected=false`, `external_system_connected=false`。
- 当前仍不宣称上线 blocker 已关闭，不宣称生产发布批准完成。
- 验证通过：v4.1 Phase 21.2 单测 5 passed。

## v4.1 Phase 21.3 Manual signoff package（当前已完成）

- 交付物：`docs/manual_signoff_package_v41.md`, `scripts/manual_signoff_package.py`, `tests/test_manual_signoff_package_v413.py`。
- 默认输出目录：`docs/reports/manual_signoff_package/`。
- 输入为 Closure Evidence Index JSON。
- 生成 release manager、security reviewer、business owner、operations owner 所需人工复核项。
- 签核包生成完成仍保持整体 `partial` + `Manual-Review`，输出明确 `manual_signoff_required=true`, `manual_signoff_completed=false`, `auto_signed=false`。
- 检测到上游 blocked/failed、secret-like 输入、非只读报告、自动审批/自动关闭标记或 release/tag 标记时输出 `blocked`。
- 保持只读边界：不读取 Markdown 正文，不读取或输出真实 secret 原文，不自动签核，不自动批准上线，不自动关闭 blocker，不执行真实发布/回滚/外部系统连接/生产变更。
- 当前仍不宣称生产发布批准完成。
- 验证通过：v4.1 Phase 21.3 单测 5 passed。

## v4.2 Phase 22.1 Controlled production acceptance drill（当前已完成）

- 交付物：`docs/v4_2_controlled_production_acceptance_plan.md`, `docs/controlled_production_acceptance_drill_v42.md`, `scripts/controlled_production_acceptance_drill.py`, `tests/test_controlled_production_acceptance_drill_v421.py`。
- 默认输出目录：`docs/reports/controlled_production_acceptance/`。
- 覆盖 real LLM、OIDC/SSO、external MCP、PostgreSQL、Redis、业务系统、APM/logging/alerting、backup/restore/DR、capacity/load/soak、security/compliance、release/rollback gate。
- 仅消费脱敏 acceptance evidence JSON，不连接真实外部系统，不执行真实生产验收动作。
- 缺少验收证据或上游 skipped 时输出 `skipped`；证据可进入人工复核时输出 `partial` + `Manual-Review`；检测到 secret-like、真实执行/连接、release/tag、自动审批/自动关闭标记时输出 `blocked`。
- 输出明确 `real_llm_executed=false`, `external_mcp_connected=false`, `database_connected=false`, `redis_connected=false`, `business_system_connected=false`, `auto_approved=false`, `auto_closed=false`, `production_direct_launch=No-Go`。
- 当前仍不宣称真实生产验收完成，不宣称公网生产可直接上线。
- 验证通过：v4.2 Phase 22.1 单测 6 passed。

## v4.2 Phase 22.2 Acceptance drill evidence index（当前已完成）

- 交付物：`docs/acceptance_drill_evidence_index_v42.md`, `scripts/acceptance_drill_evidence_index.py`, `tests/test_acceptance_drill_evidence_index_v422.py`。
- 默认输入目录：`docs/reports/controlled_production_acceptance/`。
- 默认输出目录：`docs/reports/acceptance_drill_index/`。
- 仅扫描受控生产验收演练 JSON 报告，不读取 Markdown 报告正文，不展开证据报告内容。
- 检测到 secret-like 输入、非只读报告、真实执行/连接标记、release/tag、自动审批/自动关闭标记或上游 blocked/failed 时输出 `blocked`。
- 输出明确 `production_direct_launch=No-Go`, `auto_approved=false`, `auto_closed=false`, `real_llm_executed=false`, `external_mcp_connected=false`。
- 当前仍不宣称真实生产验收完成。
- 验证通过：v4.2 Phase 22.2 单测 5 passed。

## v4.2 Phase 22.3 Production acceptance gap register（当前已完成）

- 交付物：`docs/production_acceptance_gap_register_v42.md`, `scripts/production_acceptance_gap_register.py`, `tests/test_production_acceptance_gap_register_v423.py`。
- 默认输出目录：`docs/reports/production_acceptance_gaps/`。
- 输入为 Acceptance Drill Evidence Index JSON。
- 将 skipped/blocked 域整理为人工跟踪 gap，字段覆盖 gap id、来源、风险描述、影响范围、责任人、到期时间、补偿控制、关闭证据、状态、审批状态和下一步动作。
- 默认 gap 需要人工 owner、due_at、补偿控制和关闭证据，不自动关闭，不自动审批。
- 检测到上游 blocked/failed、secret-like 输入、非只读报告、真实执行/连接标记、release/tag、自动审批/自动关闭标记时输出 `blocked`。
- 输出明确 `production_direct_launch=No-Go`, `auto_approved=false`, `auto_closed=false`, `real_llm_executed=false`, `external_mcp_connected=false`。
- 当前仍不宣称真实生产验收完成。
- 验证通过：v4.2 Phase 22.3 单测 6 passed。

## v4.3 Phase 23.1 Operations summary v4 evidence entry（当前已完成）

- 交付物：`docs/v4_3_operational_governance_console_readiness_plan.md`, `app/api/operations.py`, `tests/test_operations_summary_v312.py`。
- `/operations/summary` 的 `observability.v4_evidence` 纳入 v4.1/v4.2 证据 runbook 与默认报告目录计数。
- 覆盖 launch blocker closure、closure evidence index、manual signoff package、controlled production acceptance、acceptance drill index、production acceptance gaps。
- 仅统计 JSON 报告数量，不读取报告正文，不连接真实外部系统，不执行真实 LLM，不自动审批，不自动关闭 blocker/gap。
- `last_known_report_counts` 新增 `v4_evidence_reports`。
- 当前仍不宣称真实生产验收完成，不宣称运营台具备生产级全量治理能力。
- 验证通过：operations summary 回归 2 passed, 1 warning。

## v4.3 Phase 23.2 Frontend v4 evidence read-only view（当前已完成）

- 交付物：`frontend/src/types/api.ts`, `frontend/src/app/operations/page.tsx`, `docs/v4_3_operational_governance_console_readiness_plan.md`。
- 前端 `/operations` 已展示 `observability.v4_evidence` 的模式、边界、总 JSON 报告数和各证据入口 runbook/目录计数。
- 页面仅展示后端聚合的结构化元数据，不读取报告正文。
- 不新增生成、删除、清理、审批、关闭 blocker/gap 或触发验收的按钮。
- 保持默认 fake/offline，不触发真实 LLM，不连接真实外部系统，不输出 secret 原文。
- 当前仍不宣称真实生产验收完成，不宣称运营台具备生产级全量治理能力。

## v4.3 Phase 23.3 Operations governance empty/status semantics polish（当前已完成）

- 交付物：`frontend/src/app/operations/page.tsx`, `docs/v4_3_operational_governance_console_readiness_plan.md`。
- `/operations` 已新增 v4 evidence entry state：`directory_missing`, `no_json_reports`, `metadata_available`。
- `metadata_available` 仅表示目录中存在 JSON 元数据，不代表验收通过。
- 页面已补充 `skipped`, `blocked`, `partial`, `success` 的运营语义；`partial/success` 仍不等于生产上线批准。
- 保持只读边界：不读取报告正文，不触发真实 LLM，不连接真实外部系统，不输出 secret 原文。
- 当前仍不宣称真实生产验收完成，不宣称运营台具备生产级全量治理能力。

## v4.3.0 release prep（当前已完成）

- 版本已同步到 `4.3.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、相关测试断言。
- 已新增 `RELEASE_NOTES_v4.3.0.md`。
- 已新增 `docs/release_review_v4.3_operational_governance_console_readiness.md`。
- Phase 20.1~23.4 纳入 v4.3.0 release prep 范围。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；默认不连接真实外部系统。
- 不宣称公网生产可直接上线，不宣称真实 LLM/MCP/IdP/PostgreSQL/Redis/业务系统生产验收完成，不宣称生产级 SSO/OIDC、多租户、复杂 BI、企业级 SRE/DR/容量验收完成。

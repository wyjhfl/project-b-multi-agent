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

## v3.1 产品化增强路线说明（当前）

- v3.1 采用分阶段推进，Phase 11.1~11.5 已完成，当前处于 v3.1.0 release prep。
- 默认开发模板仍是 `docker-compose.yml`，用于本地离线开发与演示。
- 生产试点模板通过 `docker-compose.prod.yml` 叠加，不替换默认开发路径。
- 当前回归基线：754 passed, 4 skipped（默认 real_llm 用例 skip）。

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
- v3.2 规划文档：`docs/v3_2_acceptance_observability_plan.md`（当前版本仍为 3.1.0，不改版本号、不打 tag、不创建 Release）。
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

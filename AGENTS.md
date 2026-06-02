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

## v3.5.0 release prep（当前）

- 规划文档：`docs/v3_5_controlled_pilot_expansion_plan.md`。
- 生产级后续路线图：`docs/enterprise_production_landing_roadmap.md`。
- v3.5 定位：Controlled Pilot Expansion & Evidence Operations。
- release-prep 阶段版本已同步为 `3.5.0`。
- 已新增发布材料：`RELEASE_NOTES_v3.5.0.md`、`docs/release_review_v3.5_controlled_pilot_expansion.md`。
- 本轮不打 `v3.5.0` tag，不创建 GitHub Release，不移动历史 tag。
- `v3.4.0` GitHub Release 已完成，`v3.4.0/v3.3.0/v3.2.0/v3.1.0/v3.0.0` tags 保持不变。
- 保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，默认不执行真实外网 LLM，不输出真实 secret 原文。
- 不宣称公网生产直上，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 已完成，不宣称多租户/复杂 BI 全量完成。
- Go/No-Go：可以进入 v3.5.0 tag 前最终复核；是否打 tag/创建 Release 需用户单独确认。

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
- 保持只读边界：不记录真实 secret 原文、不执行真实外网 LLM、不改版本号、不打 tag、不创建 Release。
- 当前版本在 release prep 阶段已同步为 `3.5.0`；本阶段未打 tag，未创建 Release。

## v3.5 Phase 15.5 Pilot closeout report pack（当前）

- 已新增试点收口报告 runbook：`docs/pilot_closeout_report_pack_v35.md`。
- 已新增只读收口报告脚本：`scripts/pilot_closeout_report_pack.py`。
- 已新增测试：`tests/test_pilot_closeout_report_pack_v355.py`。
- 默认输出目录：`docs/reports/pilot_closeout/`。
- 支持汇总 pilot handoff、evidence archive、optional integration readiness、operator scoring、controlled integration dry-run、governance exception register 的 JSON 元数据。
- 报告包包含 executive summary、evidence summary、known limitations、Go/No-Go、next actions 和 boundary declarations。
- 对所有 `skipped/blocked/partial` 项保持原始解释，不做假通过。
- 保持只读边界：不读取报告正文、不写业务数据、不改版本号、不打 tag、不创建 Release、不执行真实外网 LLM、不输出真实 secret 原文。
- 当前版本在 release prep 阶段已同步为 `3.5.0`；本阶段未打 tag，未创建 Release。

## v3.5 Phase 15.6 release prep（当前）

- 已同步版本到 `3.5.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、脚本 version markers、相关测试断言。
- 已新增 `RELEASE_NOTES_v3.5.0.md`。
- 已新增 `docs/release_review_v3.5_controlled_pilot_expansion.md`。
- Phase 15.1~15.5 纳入 v3.5.0 release prep 范围。
- release prep 当轮不打 tag、不创建 GitHub Release、不移动历史 tag。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；不执行真实外网 LLM。
- Go/No-Go：可以进入 v3.5.0 tag 前最终复核；是否打 tag/创建 Release 需用户单独确认。

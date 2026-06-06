# 企业生产落地后续路线图

## 当前 v3.7 推进状态

- v3.7 Phase 17.1 External integration baseline inventory 已完成。
- v3.7 Phase 17.2 External MCP acceptance gate 已完成。
- v3.7 Phase 17.3 Real LLM provider acceptance gate 已完成。
- v3.7 Phase 17.4 Store and Redis production readiness drill 已完成：新增 `docs/store_redis_readiness_drill_v37.md`、`scripts/store_redis_readiness_drill.py`、`tests/test_store_redis_readiness_drill_v374.py`。
- Phase 17.4 仅做只读生产准备演练，不连接真实 PostgreSQL/Redis，不执行 Alembic migration，不写业务/审计/指标数据，不输出 secret 原文。
- v3.7 Phase 17.5 Business system integration safety checklist 已完成：新增 `docs/business_system_integration_safety_checklist_v37.md`、`scripts/business_system_integration_safety_checklist.py`、`tests/test_business_system_integration_safety_checklist_v375.py`。
- Phase 17.5 仅做真实业务系统集成前只读安全清单，不连接真实业务系统，不执行真实读写，不创建/更新/删除业务数据，不输出 secret 原文。
- v3.7 Phase 17.6 release prep 已完成：版本同步到 `3.7.0`，新增 `RELEASE_NOTES_v3.7.0.md` 与 `docs/release_review_v3.7_external_integration_real_provider_acceptance.md`。
- 当前仍不宣称 PostgreSQL、Redis、多实例限流、真实 MCP、真实 LLM 或业务系统生产验收完成；v3.7.0 tag 和 GitHub Release 需用户单独确认。

## 定位

本文面向“生产级、可落地企业项目”的后续路线规划，从技术总监视角区分当前已经具备的工程化能力、仍缺少生产验收的能力，以及后续阶段拆分。

当前项目可以作为企业内网受控试点与准生产演示基础继续推进，但不得直接包装为“生产级全量完成”。生产上线前仍必须完成身份、租户边界、外部集成、真实 LLM、可观测性、灾备、安全合规、发布门禁和容量压测等专项验收。

## 当前基线

- `v3.6.0` release prep 已完成，本地提交已创建；当前环境 GitHub HTTPS 推送不可用，远端同步需网络恢复后执行。
- v3.7 已进入 External Integration & Real Provider Acceptance 规划与只读基线阶段。
- v3.7 Phase 17.1 External integration baseline inventory 已完成。
- v3.7 Phase 17.2 External MCP acceptance gate 已完成。
- v3.7 Phase 17.3 Real LLM provider acceptance gate 已完成。
- 当前建议继续推进 Phase 17.4 Store and Redis production readiness drill。
- 默认路径继续保持 fake/offline，默认 pytest/CI 不调用真实 LLM。
- 真实 LLM、真实外部 MCP、OIDC/SSO、PostgreSQL、Redis 等能力只允许在显式 opt-in 与人工受控条件下验收。

## 已完成能力

- Harness、AgentKernel、规则型 Multi-Agent 编排、NL2SQL、审批、人审恢复、审计、指标、短期记忆、SkillRegistry、自检等核心工程骨架已形成。
- MCP stdio real protocol path 已具备最小协议链路，但默认仍为 fake 模式，真实外部 MCP 生产验收未完成。
- LLM Provider、预算、缓存、fallback、可选 judge smoke 与 preflight 已具备受控验收入口，但不等于真实 LLM 生产验收完成。
- 运营台、审批台、观测台、LLM Pilot 页面、pilot evidence 只读 API、operations summary 等试点级前端与后端闭环已形成。
- CORS、安全响应头、请求大小限制、进程内限流、基础滥用防护、结构化日志与脱敏、审计导出边界、OIDC 最小骨架已实现。
- v3.1 到 v3.5 已持续补强演示 seed、E2E、acceptance snapshot、demo artifact、failure diagnostics、report index、config drift、governance summary、live drill、incident rehearsal、evidence archive、optional integration readiness、handoff、evidence comparison、operator scoring 等证据运营能力。

## 仍缺生产验收的能力

- 生产级 SSO/OIDC：真实 IdP 联调、登录/登出、会话、token 生命周期、client secret 管理、JWKS 轮换、失败路径与审计仍需验收。
- 租户/组织边界：组织、租户、项目、用户、角色、资源归属、数据隔离、审计隔离和跨租户访问防护仍需专项设计与测试。
- 真实外部 MCP 与业务系统集成：外部工具 allowlist、网络边界、超时、重试、幂等、熔断、审批、审计、失败恢复与回放证据仍需生产级验收。
- 真实 LLM 生产验收：provider SLA、模型选择、token/cost 上限、缓存命中、fallback、prompt 注入防护、PII 脱敏、输出校验、失败降级和账单证据仍需独立验收。
- 密钥轮换：API key、client_secret、JWT_SECRET、DATABASE_URL、REDIS_URL 等敏感配置的创建、轮换、撤销、泄漏响应和审计流程仍需落地。
- 集中日志、APM 与告警：当前结构化日志和指标不足以替代企业级集中观测、链路追踪、告警分级、值班响应和 SLO 管理。
- 备份恢复 RTO/RPO：PostgreSQL、SQLite demo、审计、证据报告、配置模板与对象存储备份策略仍需定义 RTO/RPO 并演练。
- 灾备演练：服务不可用、数据库不可用、Redis 不可用、IdP 不可用、LLM provider 不可用、外部 MCP 不可用、回滚失败等场景仍需演练。
- 审计合规：审计留存周期、导出脱敏、访问授权、证据链完整性、合规复核和例外审批仍需形成制度化证据。
- 发布门禁与回滚：生产变更审批、部署前检查、迁移检查、蓝绿/灰度策略、回滚脚本、回滚验收和变更记录仍需落地。
- 容量压测：并发用户、请求峰值、工具调用、NL2SQL、审批恢复、审计写入、日志吞吐、缓存和限流策略仍需压测。
- 权限治理：角色矩阵、最小权限、权限申请、定期复核、离职回收、特权账户审计仍需企业级闭环。

## 路线原则

- 不把当前项目直接宣称为公网生产可直接上线。
- 不宣称真实 LLM 生产验收已经完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- 不移动、删除或重建任何历史 tag。
- 不提交真实密钥、Token、API Key、client_secret、JWT_SECRET、DATABASE_URL、REDIS_URL 或 REDIS_URL 实际值。
- 所有真实 provider、真实 IdP、真实外部 MCP、真实业务系统接入都必须显式 opt-in，并形成独立验收证据。
- 默认 fake/offline 开发路径必须保留，默认 pytest/CI 不调用真实外部 LLM。

## v3.5：受控试点证据运营收口

### 目标

完成企业内网受控试点前的证据运营闭环，让管理层、平台团队、运维团队和安全团队可以基于一致证据判断下一阶段是否具备进入企业身份、租户边界和真实集成验收的条件。

### 交付物

- Phase 15.3 Controlled integration dry-run checklist。
- Phase 15.4 Governance exception register。
- Phase 15.5 Pilot closeout report pack。
- Phase 15.6 v3.5 release prep。
- 统一汇总 evidence comparison、operator drill scoring、optional integration readiness、incident rehearsal、pilot handoff 和 governance exception。

### 验收命令/证据

```powershell
python -m pytest tests/test_pilot_evidence_comparison_v351.py tests/test_operator_drill_scoring_v352.py -q
python -m pytest tests/test_optional_integration_readiness_v344.py tests/test_runtime_hardening_v055.py -q
docker compose config
```

验收证据应包括 dry-run checklist JSON/Markdown、governance exception register、pilot closeout report、release review 和 release notes。缺少 opt-in 条件时必须记录为 `skipped`，不得伪造成 `success`。

### 不做什么

- 不执行真实外网 LLM 生产验收。
- 不连接真实外部 MCP 或真实业务系统做生产验收。
- 不实现生产级 SSO/OIDC 或多租户。
- 不创建或移动历史 tag，除非进入明确的 release prep/tag 流程并由用户手动处理。

### Go/No-Go

- Go：可以进入 v3.6 企业身份与租户边界专项设计和验收。
- No-Go：如果 dry-run、scoring、handoff 或 exception register 存在未解释的 `blocked/failed`，不得进入真实集成验收。

## v3.6：Enterprise Identity & Tenant Boundary

### 目标

建立企业身份、组织、租户和权限边界的生产级基础，明确用户、角色、租户、资源、审计和配置的隔离规则。

### 交付物

- 生产级 OIDC/SSO 联调方案与真实 IdP 验收记录。
- 租户、组织、项目、用户、角色和资源归属模型。
- RBAC 权限矩阵、最小权限策略、权限申请与定期复核流程。
- token 生命周期、会话管理、登出、JWKS 轮换、client_secret 轮换和失败路径测试。
- 跨租户访问防护测试、审计隔离测试和安全回归用例。

### 验收命令/证据

```powershell
python -m pytest tests/test_auth_rbac*.py -q
python -m pytest tests/test_oidc*.py -q
python -m pytest tests/test_audit*.py -q
docker compose config
```

证据必须包含真实 IdP opt-in 演练记录、权限矩阵评审记录、跨租户访问拒绝证据、密钥轮换演练记录和审计脱敏导出样例。

### 不做什么

- 不把最小 OIDC 骨架宣称为生产级 SSO/OIDC 完成。
- 不默认启用 auth_enabled 或 rbac_enabled 破坏离线演示路径。
- 不输出 client_secret、JWT_SECRET 或任何 token 原文。
- 不在未完成隔离测试前开放多租户生产承诺。

### Go/No-Go

- Go：真实 IdP 登录、权限拒绝、跨租户隔离、审计脱敏和密钥轮换均有可复核证据。
- No-Go：任一跨租户访问、权限绕过、secret 泄漏或审计缺失问题未关闭。

## v3.7：External Integration & Real Provider Acceptance

### 目标

完成真实外部 MCP、业务系统、真实 LLM provider、PostgreSQL、Redis 等可选集成的受控生产验收，形成可回放证据与失败降级策略。

### 交付物

- 外部 MCP allowlist、命令白名单、超时、重试、熔断、审批和审计策略。
- 真实业务系统集成验收记录，包括只读/写入边界、幂等、失败恢复和回滚证据。
- 真实 LLM provider 生产验收包，包括 preflight、smoke、budget、cache、fallback、PII 脱敏、prompt injection guard 和输出校验。
- PostgreSQL Store、Redis、NoopRedisClient fallback、迁移和连接失败路径验收。
- 集成风险登记表、例外审批和供应商 SLA 记录。
- Phase 17.1 已新增 `docs/external_provider_acceptance_inventory_v37.md`、`scripts/external_provider_acceptance_inventory.py`、`tests/test_external_provider_acceptance_inventory_v371.py`，用于只读盘点 external MCP、real LLM provider、LLM judge、PostgreSQL、Redis、deployment guard、tool approval audit 和 frontend offline build。
- Phase 17.2 已新增 `docs/external_mcp_acceptance_gate_v37.md`、`scripts/external_mcp_acceptance_gate.py`、`tests/test_external_mcp_acceptance_gate_v372.py`，用于只读复核 real mode opt-in、command allowlist、tool allowlist、超时、生命周期、审批和审计边界。
- Phase 17.3 已新增 `docs/real_llm_provider_acceptance_gate_v37.md`、`scripts/real_llm_provider_acceptance_gate.py`、`tests/test_real_llm_provider_acceptance_gate_v373.py`，用于只读复核 preflight、smoke opt-in、budget/cache/fallback、PII/prompt guardrails、report redaction、judge acceptance 和 evidence index。

### 验收命令/证据

```powershell
python -m pytest tests/test_mcp*.py tests/test_llm*.py -q
python -m pytest tests/test_store*.py tests/test_redis*.py -q
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

真实 provider 验收必须单独 opt-in，并产出脱敏报告；默认测试与 CI 仍不得调用真实 LLM 或真实外部 MCP。

### 不做什么

- 不把 fake MCP fixture 验收宣称为真实外部 MCP 生产验收完成。
- 不把 opt-in smoke 宣称为真实 LLM 生产验收完成。
- 不绕过后端 ToolGateway、PolicyEngine、审批链路或审计链路。
- 不将真实业务系统写入动作纳入默认演示路径。

### Go/No-Go

- Go：真实 provider 与外部系统的成功路径、失败路径、降级路径、审批链路和审计证据齐全。
- No-Go：存在无法审计的外部调用、无法控制的成本风险、无回滚策略的写入集成或 secret 暴露风险。

## v3.8：SRE Observability & DR

### 目标

把试点级运行观测提升为企业 SRE 可接管的生产运行体系，覆盖集中日志、APM、告警、容量、备份恢复、灾备和演练。

### 交付物

- 集中日志接入方案、字段脱敏策略、日志留存策略和查询手册。
- APM/Tracing 指标方案，覆盖 API、工具调用、LLM provider、MCP、数据库、Redis、审批和审计。
- SLO/SLI、告警分级、值班响应、升级路径和 incident runbook。
- 容量压测计划，覆盖并发、峰值、长任务、审计写入、日志吞吐、缓存命中和限流。
- 备份恢复策略，明确 PostgreSQL、审计、证据报告、配置模板和运行数据的 RTO/RPO。
- 灾备演练记录，覆盖服务、数据库、Redis、IdP、LLM provider、MCP 和网络异常。

### 验收命令/证据

```powershell
python -m pytest tests/test_metrics*.py tests/test_audit*.py -q
python scripts/failure_diagnostics.py --output-dir docs/reports/failure_diagnostics
docker compose config
```

还应补充压测报告、APM 截图或导出摘要、告警触发记录、备份恢复演练记录、灾备演练记录和 RTO/RPO 达成证据。

### 不做什么

- 不把本地 metrics store 等同于企业级 APM。
- 不把文档化备份清单等同于已完成真实 RTO/RPO 验收。
- 不在未压测前承诺生产容量。
- 不删除用户数据或自动清理报告作为演练手段。

### Go/No-Go

- Go：关键 SLO、告警、备份恢复、灾备和容量指标均有演练证据。
- No-Go：无法证明 RTO/RPO、容量上限、告警触达或关键链路恢复能力。

## v3.9：Compliance Security Hardening

### 目标

完成面向企业合规、安全治理和发布门禁的加固，降低上线前的审计、权限、密钥、数据和变更风险。

### 交付物

- 审计合规矩阵，覆盖访问、审批、工具调用、LLM 调用、MCP 调用、配置变更、发布和导出。
- 密钥管理与轮换流程，覆盖创建、存储、轮换、撤销、泄漏响应和审计。
- 发布门禁策略，覆盖配置预检、迁移预检、测试门禁、安全扫描、合规签核和变更审批。
- 回滚策略，覆盖应用、数据库迁移、配置、外部集成、LLM provider 和前端资产。
- 权限治理制度，覆盖权限申请、审批、定期复核、离职回收和特权账户审计。
- 安全测试包，覆盖 prompt injection、PII 泄漏、越权访问、跨租户访问、审计绕过、限流绕过和导出脱敏。

### 验收命令/证据

```powershell
python -m pytest tests/test_security*.py tests/test_audit*.py tests/test_auth_rbac*.py -q
python -m pytest tests/test_deployment*.py -q
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

证据必须包含发布门禁清单、回滚演练记录、权限复核记录、审计导出脱敏样例、安全测试报告和密钥轮换演练记录。

### 不做什么

- 不把配置模板存在视为密钥管理完成。
- 不把最小 OIDC 骨架视为生产级 SSO 合规完成。
- 不在未完成合规签核前宣称公网生产直上。
- 不输出任何真实 secret 原文。

### Go/No-Go

- Go：审计、权限、密钥、发布门禁、回滚和安全测试均有可复核证据。
- No-Go：存在未关闭的高危安全问题、无法回滚的变更、无法追踪的审计缺口或权限治理缺失。

## v4.0：Production Launch Readiness Review

### 目标

进行正式生产上线前的 Launch Readiness Review，汇总 v3.5 到 v3.9 的验收证据，形成企业内部 Go/No-Go 决策。

### 交付物

- 生产上线评审报告。
- 架构和安全最终复核记录。
- 真实 SSO/OIDC、租户边界、真实 LLM、真实 MCP、业务系统集成、SRE、DR、合规、安全和发布门禁证据索引。
- 生产 runbook、回滚 runbook、incident runbook、值班表和升级路径。
- 未完成项、风险例外、责任人、到期时间和补偿控制。
- 上线窗口、回滚窗口、冻结窗口和沟通计划。

### 验收命令/证据

```powershell
python -m pytest -q
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
python scripts/evidence_archive_manifest.py --output-dir docs/reports/evidence_archive
```

最终证据应包括完整测试报告、部署门禁结果、压测报告、灾备演练记录、回滚演练记录、审计合规评审、权限治理评审、密钥轮换记录和真实 provider 验收报告。

### 不做什么

- 不用文档口径替代真实生产验收。
- 不把 skipped、blocked 或 partial 项伪造成 success。
- 不在未关闭 Go/No-Go 阻断项前发布生产上线结论。
- 不移动或重建历史 release tag。

### Go/No-Go

- Go：所有生产阻断项关闭，剩余风险均有责任人、到期时间、补偿控制和管理层签核。
- No-Go：存在未关闭的身份、租户、外部集成、真实 LLM、安全、审计、灾备、容量、发布门禁或回滚阻断项。

## v4.1：Evidence Execution & Closure Pack

### 目标

承接 v4.0 Production Launch Readiness Review，把上线阻断项从“登记与汇总”推进到“证据关闭工作流”。本阶段仍保持默认 fake/offline，不连接真实外部系统，不宣称生产上线完成。

### v4.1 Phase 21.1 已完成：Launch blocker closure workflow

- 已新增 `docs/v4_1_evidence_execution_closure_plan.md`。
- 已新增 `docs/launch_blocker_closure_workflow_v41.md`。
- 已新增 `scripts/launch_blocker_closure_workflow.py`。
- 已新增 `tests/test_launch_blocker_closure_workflow_v411.py`。
- 默认输出目录：`docs/reports/launch_blocker_closure/`。
- 该工作流只消费结构化 JSON 字段，判断 blocker 是否具备进入人工复核的 owner、due_at、补偿控制、证据引用、reviewer 与审批状态。
- 所有证据齐全时仍输出 `partial`，只表示 `review_ready`，不自动关闭 blocker，不伪造人工审批，不宣称生产 Go。
- 保持 `production_direct_launch=No-Go`、`auto_approved=false`、`auto_closed=false`。

### v4.1 Phase 21.2 已完成：Closure evidence index

- 已新增 `docs/closure_evidence_index_v41.md`。
- 已新增 `scripts/closure_evidence_index.py`。
- 已新增 `tests/test_closure_evidence_index_v412.py`。
- 默认输入目录：`docs/reports/launch_blocker_closure/`。
- 默认输出目录：`docs/reports/closure_evidence_index/`。
- 仅索引 closure workflow JSON 的结构化元数据，不读取 Markdown 报告正文，不展开证据报告内容。
- 不修改、不移动、不删除输入证据，不自动执行 retention 清理。
- 保持 `production_direct_launch=No-Go`、`auto_approved=false`、`auto_closed=false`。

### v4.1 Phase 21.3 已完成：Manual signoff package

- 已新增 `docs/manual_signoff_package_v41.md`。
- 已新增 `scripts/manual_signoff_package.py`。
- 已新增 `tests/test_manual_signoff_package_v413.py`。
- 默认输出目录：`docs/reports/manual_signoff_package/`。
- 基于 Closure Evidence Index 生成供 CAB / release review 人工复核使用的脱敏签核包。
- 签核包生成完成仍保持 `partial` + `Manual-Review`，不代表签核完成，不自动批准上线，不自动关闭 blocker。
- 保持 `manual_signoff_completed=false`、`auto_signed=false`、`production_direct_launch=No-Go`。

### 后续建议

- Phase 21.4：v4.1 release prep，仅在用户确认后同步版本和 release notes/review，不自动 tag 或创建 GitHub Release。

## v4.2：Controlled Production Acceptance Drills

### 目标

承接 v4.1 Evidence Execution & Closure Pack，建立受控生产验收演练包。默认仍为 fake/offline，只消费脱敏证据，不执行真实外部连接或生产动作。

### v4.2 Phase 22.1 已完成：Controlled production acceptance drill

- 已新增 `docs/v4_2_controlled_production_acceptance_plan.md`。
- 已新增 `docs/controlled_production_acceptance_drill_v42.md`。
- 已新增 `scripts/controlled_production_acceptance_drill.py`。
- 已新增 `tests/test_controlled_production_acceptance_drill_v421.py`。
- 默认输出目录：`docs/reports/controlled_production_acceptance/`。
- 覆盖 real LLM、OIDC/SSO、external MCP、PostgreSQL、Redis、业务系统、APM/logging/alerting、backup/restore/DR、capacity/load/soak、security/compliance、release/rollback gate。
- 仅消费脱敏 acceptance evidence JSON，不连接真实外部系统，不执行真实生产验收动作。
- 即使证据可进入人工复核，也保持 `partial` + `Manual-Review`，不宣称真实生产验收完成。

### v4.2 Phase 22.2 已完成：Acceptance drill evidence index

- 已新增 `docs/acceptance_drill_evidence_index_v42.md`。
- 已新增 `scripts/acceptance_drill_evidence_index.py`。
- 已新增 `tests/test_acceptance_drill_evidence_index_v422.py`。
- 默认输入目录：`docs/reports/controlled_production_acceptance/`。
- 默认输出目录：`docs/reports/acceptance_drill_index/`。
- 仅索引受控生产验收演练 JSON 的结构化元数据，不读取 Markdown 报告正文。
- 不修改、不移动、不删除输入证据，不自动批准上线。

### v4.2 Phase 22.3 已完成：Production acceptance gap register

- 已新增 `docs/production_acceptance_gap_register_v42.md`。
- 已新增 `scripts/production_acceptance_gap_register.py`。
- 已新增 `tests/test_production_acceptance_gap_register_v423.py`。
- 默认输出目录：`docs/reports/production_acceptance_gaps/`。
- 将 Acceptance Drill Evidence Index 中的 skipped/blocked 域整理为人工跟踪 gap。
- 默认 gap 需要人工 owner、due_at、补偿控制和关闭证据，不自动关闭，不自动审批。
- 保持 `production_direct_launch=No-Go`、`auto_approved=false`、`auto_closed=false`。

### 后续建议

- Phase 22.4：v4.2 release prep，仅在用户确认后同步版本和 release notes/review，不自动 tag 或创建 GitHub Release。

## v4.3：Operational Governance Console Readiness

### 目标

将 v4.1/v4.2 的上线阻断、关闭证据、人工签核、受控生产验收和验收缺口入口纳入只读运营治理视图。默认不触发真实外部系统，不读取报告正文，不执行清理、审批或关闭动作。

### v4.3 Phase 23.1 已完成：Operations summary v4 evidence entry

- 已新增 `docs/v4_3_operational_governance_console_readiness_plan.md`。
- 已增强 `/operations/summary` 的 `observability.v4_evidence` 元数据。
- 已纳入 v4.1/v4.2 证据 runbook 与默认报告目录计数。
- `last_known_report_counts` 新增 `v4_evidence_reports`。
- 仅统计 JSON 报告数量，不读取报告正文，不连接真实外部系统，不自动审批，不自动关闭 blocker/gap。

### v4.3 Phase 23.2 已完成：Frontend v4 evidence read-only view

- 已更新前端类型契约：`frontend/src/types/api.ts`。
- 已增强前端 `/operations` 页面，展示 `observability.v4_evidence` 的模式、边界、总 JSON 报告数和各证据入口 runbook/目录计数。
- 页面只消费后端结构化元数据，不读取报告正文，不新增生成、删除、清理、审批、关闭 blocker/gap 或触发验收的动作。
- 保持默认 fake/offline，不触发真实 LLM，不连接真实外部系统，不输出 secret 原文。

### v4.3 Phase 23.3 已完成：Operations governance empty/status semantics polish

- 已增强前端 `/operations` 的 v4 evidence 空态和状态语义展示。
- 已新增 entry state：`directory_missing`、`no_json_reports`、`metadata_available`。
- `metadata_available` 仅表示目录中存在 JSON 元数据，不代表验收通过。
- `skipped` 表示缺少输入或 opt-in 条件，`blocked` 表示边界违规或上游失败，`partial` 表示需要人工复核，`success` 仅代表本地脚本完成有限检查。
- `partial/success` 仍不等于生产上线批准，公网生产直上仍为 No-Go。

### v4.3 Phase 23.4 已完成：v4.3.0 release prep

- 版本已同步到 `4.3.0`。
- 已新增 `RELEASE_NOTES_v4.3.0.md`。
- 已新增 `docs/release_review_v4.3_operational_governance_console_readiness.md`。
- Phase 20.1~23.4 纳入 v4.3.0 release prep 范围。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 当前仍不宣称真实生产验收完成，不宣称公网生产可直接上线。

### 后续建议

- 进入 `v4.3.0` tag 前最终人工复核。
- 后续可进入 v4.4 或下一阶段生产验收证据闭环规划。

## 总体 Go/No-Go 口径

- 当前阶段：可继续企业内网受控试点与证据运营。
- 生产级全量完成：No-Go，仍需 v3.6 至 v4.0 专项验收。
- 公网生产直上：No-Go。
- 真实 LLM 生产验收完成：No-Go，需在 v3.7 形成独立 opt-in 生产验收证据。
- 生产级 SSO/OIDC 与多租户完成：No-Go，需在 v3.6 形成真实 IdP、权限、租户隔离和审计证据。
- 企业内网试点继续推进：Go，但必须保留默认 fake/offline 路径、脱敏边界和 skipped 语义。
### v3.8 Phase 18.1 已完成：SRE observability baseline

- 已新增 `docs/sre_observability_baseline_v38.md`、`scripts/sre_observability_baseline.py`、`tests/test_sre_observability_baseline_v381.py`。
- 默认输出目录为 `docs/reports/sre_observability_baseline/`，输出 JSON + Markdown。
- 该基线只读盘点 runtime metrics、runtime snapshot、operations summary、audit export、structured logging、failure diagnostics、backup/restore runbook、APM、告警、容量、备份与 DR 缺口。
- 默认不启动服务、不访问在线端点、不连接真实 APM/日志/告警/值班系统、不执行真实压测/备份恢复/灾备切换。
- 缺少 opt-in 条件时记录为 `skipped`，不宣称企业级 SRE、RTO/RPO、SLO/SLI、告警或生产 DR 验收完成。
### v3.8 Phase 18.2 已完成：SLO/SLI and alerting runbook pack

- 已新增 `docs/slo_alerting_runbook_pack_v38.md`、`scripts/slo_alerting_runbook_pack.py`、`tests/test_slo_alerting_runbook_pack_v382.py`。
- 默认输出目录为 `docs/reports/slo_alerting_runbook/`，输出 JSON + Markdown。
- 该 runbook 包只读盘点 SLO/SLI 指标来源、SLO 目标配置、structured logging 告警上下文、告警分级与路由、on-call 升级、alert dry-run 证据和 incident runbook 串联。
- 默认不启动服务、不访问在线端点、不连接真实告警平台、不发送真实告警、不通知真实 on-call、不调用真实 webhook。
- 缺少 opt-in 或演练证据时记录为 `skipped`，不宣称企业级 SLO/告警生产验收完成。
### v3.8 Phase 18.3 已完成：Backup/restore and DR drill evidence pack

- 已新增 `docs/backup_restore_dr_evidence_pack_v38.md`、`scripts/backup_restore_dr_evidence_pack.py`、`tests/test_backup_restore_dr_evidence_pack_v383.py`。
- 默认输出目录为 `docs/reports/backup_restore_dr_evidence/`，输出 JSON + Markdown。
- 该证据包只读盘点备份范围、部署与迁移边界、RTO/RPO 配置、备份演练证据、恢复 dry-run 证据、DR failover 证据和 runbook 串联。
- 默认不启动服务、不连接真实 PostgreSQL/Redis/对象存储、不执行真实备份/恢复/灾备切换、不执行 Alembic migration。
- 缺少 opt-in 或演练证据时记录为 `skipped`，不宣称 RTO/RPO 或生产 DR 验收完成。
### v3.8 Phase 18.4 已完成：Capacity and load-test readiness plan

- 已新增 `docs/capacity_load_test_readiness_plan_v38.md`、`scripts/capacity_load_test_readiness_plan.py`、`tests/test_capacity_load_test_readiness_plan_v384.py`。
- 默认输出目录为 `docs/reports/capacity_load_test_readiness/`，输出 JSON + Markdown。
- 该计划只读盘点关键 API 入口、流量模型目标、request guard、容量测试可观测性、load-test dry-run 证据、soak test 证据和 runbook 串联。
- 默认不启动服务、不访问在线端点、不执行真实压测、soak test、并发请求或容量探测。
- 缺少 opt-in 或报告证据时记录为 `skipped`，不宣称生产容量上限验收完成。
### v3.8.0 release prep 已完成

- 版本已同步到 `3.8.0`，新增 `RELEASE_NOTES_v3.8.0.md` 与 `docs/release_review_v3.8_sre_observability_dr.md`。
- Phase 18.1~18.4 纳入 v3.8.0 release prep 范围。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 当前仍不宣称企业级 SRE、真实 APM/告警、RTO/RPO、DR failover、生产容量上限、真实 LLM 生产验收、生产级 SSO/OIDC、多租户或复杂 BI 完成。
### v3.9 规划已开启：Compliance Security Hardening

- 已新增规划文档：`docs/v3_9_compliance_security_hardening_plan.md`。
- 当前已完成 v3.9.0 release prep，版本已同步为 `3.9.0`。
- 本轮不打 tag，不创建 GitHub Release，不移动历史 tag。
- 默认不执行真实安全扫描、真实密钥轮换、真实权限变更、真实审计导出、真实发布或真实回滚。

### v3.9 Phase 19.1 已完成：Compliance security baseline inventory

- 已新增 `docs/compliance_security_baseline_v39.md`、`scripts/compliance_security_baseline.py`、`tests/test_compliance_security_baseline_v391.py`。
- 默认输出目录为 `docs/reports/compliance_security_baseline/`，输出 JSON + Markdown。
- 该基线只读盘点 deployment guard、安全响应头、request guard、结构化日志脱敏、审计留存与导出、RBAC、OIDC、prompt injection、PII guard、跨租户审计和 release review 证据缺口。
- 默认不启动服务、不访问在线端点、不连接真实外部系统、不执行真实安全扫描、审计导出、密钥轮换、权限变更、发布或回滚。
- 缺少正式签核或演练证据时记录为 `skipped`，不宣称企业级合规安全验收完成。
### v3.9 Phase 19.2 已完成：Secret rotation and leakage response pack

- 已新增 `docs/secret_rotation_leakage_response_pack_v39.md`、`scripts/secret_rotation_leakage_response_pack.py`、`tests/test_secret_rotation_leakage_response_pack_v392.py`。
- 默认输出目录为 `docs/reports/secret_rotation_leakage_response/`，输出 JSON + Markdown。
- 该证据包只读盘点 JWT/OIDC/数据库/Redis/LLM/MCP/业务系统/告警 webhook 等 secret surface、脱敏审计边界、身份密钥生命周期、外部集成密钥边界、治理例外串联、轮换/泄漏响应/撤销恢复演练证据缺口。
- 默认不读取 `.env` 或真实 secret 值，不连接真实密钥系统，不执行真实密钥创建、轮换、撤销、禁用、泄漏扫描或告警通知。
- 缺少演练证据时记录为 `skipped`，不宣称企业级密钥治理完成。
### v3.9 Phase 19.3 已完成：Release gate and rollback governance pack

- 已新增 `docs/release_gate_rollback_governance_pack_v39.md`、`scripts/release_gate_rollback_governance_pack.py`、`tests/test_release_gate_rollback_governance_pack_v393.py`。
- 默认输出目录为 `docs/reports/release_gate_rollback_governance/`，输出 JSON + Markdown。
- 该证据包只读盘点 deployment guard、compose、Alembic、release notes、release review、变更审批、发布签核、回滚演练、治理例外和安全合规串联证据缺口。
- 默认不启动服务、不访问在线端点、不执行 git tag、GitHub Release、部署、迁移、回滚、数据恢复或外部系统调用。
- 缺少变更审批、发布签核或回滚演练证据时记录为 `skipped`，不宣称生产发布门禁或回滚验收完成。
### v3.9 Phase 19.4 已完成：Security regression and compliance evidence pack

- 已新增 `docs/security_regression_compliance_evidence_pack_v39.md`、`scripts/security_regression_compliance_evidence_pack.py`、`tests/test_security_regression_compliance_evidence_pack_v394.py`。
- 默认输出目录为 `docs/reports/security_regression_compliance_evidence/`，输出 JSON + Markdown。
- 该证据包只读盘点 prompt injection、PII 泄漏、SQL guard、边界防护、身份/RBAC、跨租户拒绝、审计导出脱敏、发布门禁和合规证据串联缺口。
- 默认不启动服务、不访问在线端点、不执行真实 SAST、DAST、依赖扫描、红队测试、外部审计或外部系统调用。
- 缺少外部安全扫描、正式安全签核或合规证据复核时记录为 `skipped`，不宣称企业级安全合规验收完成。
### v3.9.0 release prep 已完成

- 版本已同步到 `3.9.0`，新增 `RELEASE_NOTES_v3.9.0.md` 与 `docs/release_review_v3.9_compliance_security_hardening.md`。
- Phase 19.1~19.4 纳入 v3.9.0 release prep 范围。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 当前仍不宣称企业级合规、安全治理、密钥治理、发布门禁、回滚验收、真实 LLM 生产验收、生产级 SSO/OIDC、多租户或复杂 BI 完成。
### v4.0 Phase 20.1 已完成：Launch readiness evidence review pack

- 已新增 `docs/v4_0_production_launch_readiness_plan.md`、`docs/production_launch_readiness_review_v40.md`、`scripts/production_launch_readiness_review.py`、`tests/test_production_launch_readiness_review_v401.py`。
- 默认输出目录为 `docs/reports/production_launch_readiness/`，输出 JSON + Markdown。
- 该评审包只读汇总 v3.5~v3.9 试点收口、证据归档、真实 provider 验收、SRE/DR、容量、安全合规、发布门禁和回滚治理证据入口。
- 默认状态为 `partial`，Go/No-Go 建议为 `Manual-Review`，公网生产直上为 `No-Go`。
- 默认不启动服务、不访问在线端点、不连接真实外部系统、不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、审计导出、密钥轮换或权限变更。
- 缺少真实生产验收证据时保留 production blockers，不伪造成 `success`，不宣称生产上线批准完成。
- 已补强 `external_system_connected` 边界违规识别，避免真实外部系统连接标记被降级为 `partial`。
- 本阶段不改版本号，不打 tag，不创建 GitHub Release。
### v4.0 Phase 20.2 已完成：Launch blocker register

- 已新增 `docs/launch_blocker_register_v40.md`、`scripts/launch_blocker_register.py`、`tests/test_launch_blocker_register_v402.py`。
- 默认输出目录为 `docs/reports/launch_blockers/`，输出 JSON + Markdown。
- 该登记册将 Launch Readiness Review 的 production blockers 和 missing conditions 整理为人工跟踪台账，覆盖责任人、到期时间、补偿控制、关闭证据和审批状态。
- 默认无上游输入或上游 `skipped` 时输出 `skipped`；存在待关闭 blocker 时输出 `partial`；上游 `blocked/failed`、secret-like 输入、自动批准/关闭标记或边界违规时输出 `blocked`。
- 默认不启动服务、不访问在线端点、不连接真实外部系统、不执行真实生产操作。
- `auto_approved=false`、`auto_closed=false`，不自动批准上线，不自动关闭阻断项，不宣称生产 Go。
- 已补强上游 `skipped` 保留、`auto_approved/auto_closed` 阻断和 success 语义文档。
- 本阶段不改版本号，不打 tag，不创建 GitHub Release。
### v4.0 Phase 20.3 已完成：Production runbook finalization

- 已新增 `docs/production_runbook_finalization_v40.md`、`scripts/production_runbook_finalization.py`、`tests/test_production_runbook_finalization_v403.py`。
- 默认输出目录为 `docs/reports/production_runbook_finalization/`，输出 JSON + Markdown。
- 该索引汇总部署、回滚、incident、DR、密钥轮换、审计导出、SLO/告警、容量、Launch Readiness 和 blocker register 的本地 runbook 入口。
- 默认仅检查本地文件存在性和可选上游 JSON 结构化字段，不读取 Markdown 报告正文。
- 默认不启动服务、不访问在线端点、不连接真实外部系统、不执行真实生产操作。
- 输出明确 `deployment_executed=false`、`rollback_executed=false`、`alert_sent=false`、`oncall_notified=false`、`auto_approved=false`、`auto_closed=false`。
- 已补强缺少上游 Phase 20.1/20.2 JSON 时的 `skipped` 语义、Phase 20.2 blocker 计数透传、上游 Go/No-Go 透传和 audit log/export 必需入口。
- 不把 runbook 入口存在性伪造成生产 Go；本阶段不改版本号，不打 tag，不创建 GitHub Release。

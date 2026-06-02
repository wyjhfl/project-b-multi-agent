# 企业生产落地后续路线图

## 定位

本文面向“生产级、可落地企业项目”的后续路线规划，从技术总监视角区分当前已经具备的工程化能力、仍缺少生产验收的能力，以及后续阶段拆分。

当前项目可以作为企业内网受控试点与准生产演示基础继续推进，但不得直接包装为“生产级全量完成”。生产上线前仍必须完成身份、租户边界、外部集成、真实 LLM、可观测性、灾备、安全合规、发布门禁和容量压测等专项验收。

## 当前基线

- `v3.4.0` GitHub Release 已由用户手动创建，历史 tag 保持不变。
- v3.5 已进入 Controlled Pilot Expansion & Evidence Operations 阶段。
- v3.5 Phase 15.1 Pilot evidence comparison snapshot 已完成。
- v3.5 Phase 15.2 Operator drill scoring rubric 已完成。
- 当前建议继续推进 Phase 15.3 Controlled integration dry-run checklist。
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

## 总体 Go/No-Go 口径

- 当前阶段：可继续企业内网受控试点与证据运营。
- 生产级全量完成：No-Go，仍需 v3.6 至 v4.0 专项验收。
- 公网生产直上：No-Go。
- 真实 LLM 生产验收完成：No-Go，需在 v3.7 形成独立 opt-in 生产验收证据。
- 生产级 SSO/OIDC 与多租户完成：No-Go，需在 v3.6 形成真实 IdP、权限、租户隔离和审计证据。
- 企业内网试点继续推进：Go，但必须保留默认 fake/offline 路径、脱敏边界和 skipped 语义。

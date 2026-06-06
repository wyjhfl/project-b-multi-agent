# v4.0 Production Launch Readiness Review 规划

## 定位

- v4.0 = **Production Launch Readiness Review**。
- 核心目标：汇总 v3.5~v3.9 的身份、租户、外部集成、真实 LLM、SRE/DR、容量、安全合规、发布门禁和回滚证据，形成企业生产上线前 Go/No-Go 评审包。
- 当前进入 v4.0 规划与只读证据汇总阶段，不同步版本号，不打 tag，不创建 GitHub Release。

## 边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 默认不连接真实 IdP、LLM provider、外部 MCP、业务系统、PostgreSQL、Redis、APM、日志、告警、KMS、Vault、对象存储或云平台。
- 默认不执行真实部署、迁移、发布、回滚、压测、备份恢复、灾备切换、安全扫描、红队测试、审计导出、密钥轮换或权限变更。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- 不把 `skipped`、`blocked`、`partial` 或仅本地只读证据汇总伪造成生产 Go。

## Phase 20.1：Launch readiness evidence review pack（P0）

### 目标

建立生产上线前只读证据评审包，汇总本地 release/runbook/script/test 证据和可选 JSON 报告结构化字段，输出阻断项、缺失条件、Go/No-Go 建议和下一步动作。

### 交付物

- runbook：`docs/production_launch_readiness_review_v40.md`
- 只读脚本：`scripts/production_launch_readiness_review.py`
- 测试：`tests/test_production_launch_readiness_review_v401.py`
- 默认输出目录：`docs/reports/production_launch_readiness/`

### 不做什么

- 不启动服务或访问在线端点。
- 不连接真实外部系统。
- 不读取 `.env` 或真实 secret 值。
- 不执行真实生产发布、回滚、迁移、压测、备份恢复、DR failover、安全扫描或密钥轮换。
- 不自动改变最终生产 Go/No-Go 结论。

## 后续 Phase 建议

- Phase 20.2：Launch blocker register，把 v4.0 评审输出中的阻断项整理成责任人、到期时间、补偿控制和关闭证据索引。（已完成）
- Phase 20.3：Production runbook finalization，汇总部署、回滚、incident、DR、密钥轮换、审计导出和值班升级 runbook。（已完成）
- Phase 20.4：Final release gate simulation，只读检查 release notes、tag 决策、部署门禁、回滚窗口、冻结窗口和沟通计划。
- Phase 20.5：v4.0 release prep，仅在用户确认后同步版本、补 release notes/review；不自动打 tag 或创建 GitHub Release。

## Phase 20.2：Launch blocker register（P0，已完成）

### 目标

将 Phase 20.1 Launch Readiness Review 的 production blockers 和 missing conditions 整理为可人工跟踪的上线阻断项登记册。

### 交付物

- runbook：`docs/launch_blocker_register_v40.md`
- 只读脚本：`scripts/launch_blocker_register.py`
- 测试：`tests/test_launch_blocker_register_v402.py`
- 默认输出目录：`docs/reports/launch_blockers/`

### 执行状态

- 默认无上游输入时输出 `skipped`，不伪造成 `success`。
- 从 Launch Readiness Review 输入生成 blocker register 时，所有 blocker 默认需要人工责任人、到期时间、补偿控制和关闭证据。
- 上游 `blocked/failed`、secret-like 输入、非只读输入、意外真实外部执行、意外 tag/release 标记会使登记册进入 `blocked`。
- `auto_approved=false`，`auto_closed=false`，不自动批准上线，不自动关闭阻断项。
- 本阶段不改版本号，不打 tag，不创建 GitHub Release。

## Phase 20.3：Production runbook finalization（P1，已完成）

### 目标

汇总生产上线前部署、回滚、incident、DR、密钥轮换、审计导出、SLO/告警、容量、Launch Readiness 和 blocker register 的本地 runbook 入口，生成只读完整性索引。

### 交付物

- runbook：`docs/production_runbook_finalization_v40.md`
- 只读脚本：`scripts/production_runbook_finalization.py`
- 测试：`tests/test_production_runbook_finalization_v403.py`
- 默认输出目录：`docs/reports/production_runbook_finalization/`

### 执行状态

- 默认仅检查本地文件存在性和可选上游 JSON 结构化字段。
- 默认输出 `partial` 或 `skipped`，不把 runbook 入口存在性伪造成生产 Go。
- 上游 `blocked/failed`、secret-like 输入、非只读输入、意外真实执行、自动批准/关闭标记会使索引进入 `blocked`。
- 缺少上游 Phase 20.1/20.2 JSON 时输出 `skipped`，并透传 blocker 计数与上游 Go/No-Go。
- audit log/export 文档与审计留存导出测试纳入必需入口。
- 输出明确 `deployment_executed=false`、`rollback_executed=false`、`alert_sent=false`、`oncall_notified=false`、`auto_approved=false`、`auto_closed=false`。
- 本阶段不改版本号，不打 tag，不创建 GitHub Release。

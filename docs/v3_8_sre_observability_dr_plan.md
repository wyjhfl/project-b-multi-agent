# v3.8 SRE Observability & DR 规划

## 定位

- v3.8 = **SRE Observability & DR**。
- 核心目标：把当前试点级运行观测提升为企业 SRE 可接管的生产运行体系准备，覆盖集中日志、APM/Tracing、SLO/SLI、告警、容量、备份恢复、灾备和演练证据。
- 当前已进入 v3.8.0 release prep，版本已同步为 `3.8.0`。
- 本轮不打 tag、不创建 GitHub Release、不移动历史 tag。

## 边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 默认不连接真实 APM、日志平台、告警平台、值班系统或对象存储。
- 默认不执行真实压测、备份恢复、灾备切换或报告清理。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码或告警 webhook 原文。
- 不把本地 metrics store、只读脚本或 runbook 宣称为企业级 SRE 验收完成。
- 不宣称 RTO/RPO、SLO/SLI、容量上限或告警触发能力已生产验收完成。

## Phase 18.1：SRE observability baseline（P0）

### 目标

建立 SRE 观测基线盘点，明确当前 metrics、runtime snapshot、operations summary、audit export、structured logging、failure diagnostics、backup/restore runbook 和 DR 证据缺口。

### 交付物

- runbook：`docs/sre_observability_baseline_v38.md`
- 只读脚本：`scripts/sre_observability_baseline.py`
- 测试：`tests/test_sre_observability_baseline_v381.py`
- 默认输出目录：`docs/reports/sre_observability_baseline/`

### 不做什么

- 不启动服务。
- 不访问在线 `/health`、`/metrics`、`/operations` 或 `/runtime/snapshot` 端点。
- 不连接真实 APM、日志平台、告警平台或值班系统。
- 不执行真实压测、备份恢复或灾备切换。

## Phase 18.2：SLO/SLI and alerting runbook pack（P1）

建立 SLO/SLI、告警分级、值班响应、升级路径和 incident runbook 包。默认只读，不触发真实告警。

## Phase 18.3：Backup/restore and DR drill evidence pack（P1）

建立备份恢复与灾备演练证据包，明确 PostgreSQL、SQLite demo、审计、指标、报告和配置模板的 RTO/RPO 证据要求。默认不删除数据、不执行真实恢复。

## Phase 18.4：Capacity and load-test readiness plan（P2）

建立容量与压测准备计划，覆盖并发用户、请求峰值、工具调用、NL2SQL、审批恢复、审计写入、日志吞吐、缓存命中和限流策略。默认不执行真实压测。

## Phase 18.5：v3.8 release prep（P2）

完成 v3.8 release prep，同步版本号、release notes、release review 和 tag 决策前复核材料。本轮 release prep 不自动打 tag、不创建 GitHub Release。
## Phase 18.1 执行状态（已完成）

- 已新增 runbook：`docs/sre_observability_baseline_v38.md`。
- 已新增只读脚本：`scripts/sre_observability_baseline.py`。
- 已新增测试：`tests/test_sre_observability_baseline_v381.py`。
- 默认输出目录：`docs/reports/sre_observability_baseline/`。
- 默认执行结果在缺少 SRE/APM/告警/容量/备份/DR opt-in 条件时为 `skipped`，并保留缺失条件列表。
- 验证通过：
  - `python -m pytest tests/test_sre_observability_baseline_v381.py -q`
  - `python scripts/sre_observability_baseline.py --output-dir <temp>`
- 本阶段未启动服务，未访问在线端点，未连接真实 APM/日志/告警/值班系统，未执行真实压测、备份恢复或灾备切换。
- 下一步建议进入 Phase 18.2：SLO/SLI and alerting runbook pack。
## Phase 18.2 执行状态（已完成）

- 已新增 runbook：`docs/slo_alerting_runbook_pack_v38.md`。
- 已新增只读脚本：`scripts/slo_alerting_runbook_pack.py`。
- 已新增测试：`tests/test_slo_alerting_runbook_pack_v382.py`。
- 默认输出目录：`docs/reports/slo_alerting_runbook/`。
- 默认执行结果在缺少 SLO/告警/on-call/dry-run opt-in 或演练证据时为 `skipped`，并保留缺失条件列表。
- 验证通过：
  - `python -m pytest tests/test_slo_alerting_runbook_pack_v382.py -q`
  - `python scripts/slo_alerting_runbook_pack.py --output-dir <temp>`
- 本阶段未启动服务，未访问在线端点，未连接真实 APM/日志/告警/值班系统，未发送真实告警，未通知真实 on-call，未调用真实 webhook。
- 下一步建议进入 Phase 18.3：Backup/restore and DR drill evidence pack。
## Phase 18.3 执行状态（已完成）

- 已新增 runbook：`docs/backup_restore_dr_evidence_pack_v38.md`。
- 已新增只读脚本：`scripts/backup_restore_dr_evidence_pack.py`。
- 已新增测试：`tests/test_backup_restore_dr_evidence_pack_v383.py`。
- 默认输出目录：`docs/reports/backup_restore_dr_evidence/`。
- 默认执行结果在缺少备份/恢复/DR opt-in 或演练证据时为 `skipped`，并保留缺失条件列表。
- 验证通过：
  - `python -m pytest tests/test_backup_restore_dr_evidence_pack_v383.py -q`
  - `python scripts/backup_restore_dr_evidence_pack.py --output-dir <temp>`
- 本阶段未启动服务，未连接真实 PostgreSQL/Redis/对象存储，未执行真实备份、恢复、灾备切换或 Alembic migration。
- 下一步建议进入 Phase 18.4：Capacity and load-test readiness plan。
## Phase 18.4 执行状态（已完成）

- 已新增 runbook：`docs/capacity_load_test_readiness_plan_v38.md`。
- 已新增只读脚本：`scripts/capacity_load_test_readiness_plan.py`。
- 已新增测试：`tests/test_capacity_load_test_readiness_plan_v384.py`。
- 默认输出目录：`docs/reports/capacity_load_test_readiness/`。
- 默认执行结果在缺少容量/压测/soak opt-in 或报告证据时为 `skipped`，并保留缺失条件列表。
- 验证通过：
  - `python -m pytest tests/test_capacity_load_test_readiness_plan_v384.py -q`
  - `python scripts/capacity_load_test_readiness_plan.py --output-dir <temp>`
- 本阶段未启动服务，未访问在线端点，未执行真实压测、soak test、并发请求或容量探测。
- 下一步建议进入 Phase 18.5：v3.8 release prep。
## Phase 18.5 执行状态（已完成）

- 版本已同步到 `3.8.0`。
- 已新增 release notes：`RELEASE_NOTES_v3.8.0.md`。
- 已新增 release review：`docs/release_review_v3.8_sre_observability_dr.md`。
- Phase 18.1~18.4 纳入 v3.8.0 release prep 范围。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline，不连接真实 APM、日志、告警、对象存储、PostgreSQL、Redis、IdP、外部 MCP 或业务系统。
- 不宣称公网生产可直接上线，不宣称企业级 SRE、RTO/RPO、DR、容量上限、真实 LLM 生产验收、生产级 SSO/OIDC 或多租户完成。

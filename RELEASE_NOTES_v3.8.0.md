# Project B v3.8.0 - SRE Observability & DR

## 定位

v3.8.0 聚焦 SRE Observability & DR，把 v3.7 外部集成验收之后的运行体系继续向企业内网试点可接管方向推进。该版本仍保持默认 fake/offline，默认测试与 CI 不调用真实 LLM，不连接真实外部 MCP、真实业务系统、真实 PostgreSQL、Redis、APM、日志平台、告警平台、对象存储或 IdP。

## 交付范围

- Phase 18.1：SRE observability baseline
  - `docs/sre_observability_baseline_v38.md`
  - `scripts/sre_observability_baseline.py`
  - `tests/test_sre_observability_baseline_v381.py`
- Phase 18.2：SLO/SLI and alerting runbook pack
  - `docs/slo_alerting_runbook_pack_v38.md`
  - `scripts/slo_alerting_runbook_pack.py`
  - `tests/test_slo_alerting_runbook_pack_v382.py`
- Phase 18.3：Backup/restore and DR drill evidence pack
  - `docs/backup_restore_dr_evidence_pack_v38.md`
  - `scripts/backup_restore_dr_evidence_pack.py`
  - `tests/test_backup_restore_dr_evidence_pack_v383.py`
- Phase 18.4：Capacity and load-test readiness plan
  - `docs/capacity_load_test_readiness_plan_v38.md`
  - `scripts/capacity_load_test_readiness_plan.py`
  - `tests/test_capacity_load_test_readiness_plan_v384.py`
- Phase 18.5：v3.8.0 release prep
  - 版本同步到 `3.8.0`
  - `docs/release_review_v3.8_sre_observability_dr.md`

## 边界

- 不启动服务作为脚本默认行为。
- 不访问在线 `/health`、`/metrics`、`/operations` 或 `/runtime/snapshot`。
- 不连接真实 APM、日志平台、告警平台、值班系统、对象存储、PostgreSQL、Redis、IdP、LLM provider、外部 MCP 或业务系统。
- 不执行真实告警、on-call 通知、incident 升级、压测、soak test、备份恢复、灾备切换或 Alembic migration。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码、告警 webhook 或压测目标 URL 原文。
- 缺少 opt-in 或演练证据时记录为 `skipped`，不得伪造成 `success`。

## 未完成项

- 企业级 APM/Tracing、集中日志、告警平台和 on-call 系统真实接入尚未完成。
- 真实 SLO/SLI、错误预算、告警触发、on-call 响应和 incident 升级生产验收尚未完成。
- 真实备份恢复、RTO/RPO 达成证据和 DR failover 生产验收尚未完成。
- 真实容量压测、soak test 和生产容量上限验收尚未完成。
- 公网生产直上、真实 LLM 生产验收、生产级 SSO/OIDC、多租户和复杂 BI 仍不宣称完成。

## 验证

```powershell
python -m pytest tests/test_sre_observability_baseline_v381.py tests/test_slo_alerting_runbook_pack_v382.py tests/test_backup_restore_dr_evidence_pack_v383.py tests/test_capacity_load_test_readiness_plan_v384.py -q
python -m pytest tests/test_runtime_persistence_v05.py tests/test_runtime_hardening_v055.py tests/test_operations_summary_v312.py tests/test_failure_diagnostics_v324.py tests/test_request_guards_v72.py -q
git diff --check
```

最终全量回归：`900 passed, 4 skipped, 2 warnings`。

本轮 release prep 不打 `v3.8.0` tag，不创建 GitHub Release，不移动历史 tag。

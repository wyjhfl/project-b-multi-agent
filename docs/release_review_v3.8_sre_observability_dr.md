# v3.8.0 Release Review - SRE Observability & DR

## Scope

v3.8.0 纳入 Phase 18.1~18.4 的 SRE 观测、SLO/告警、备份恢复/DR、容量压测准备能力，并完成 Phase 18.5 release prep。目标是形成企业内网试点 SRE 接管前的只读证据基线和 runbook 包，不执行真实外部系统操作。

## Changed Files

- 文档：
  - `RELEASE_NOTES_v3.8.0.md`
  - `docs/v3_8_sre_observability_dr_plan.md`
  - `docs/sre_observability_baseline_v38.md`
  - `docs/slo_alerting_runbook_pack_v38.md`
  - `docs/backup_restore_dr_evidence_pack_v38.md`
  - `docs/capacity_load_test_readiness_plan_v38.md`
  - `docs/production_readiness_checklist.md`
  - `docs/enterprise_production_landing_roadmap.md`
- 脚本：
  - `scripts/sre_observability_baseline.py`
  - `scripts/slo_alerting_runbook_pack.py`
  - `scripts/backup_restore_dr_evidence_pack.py`
  - `scripts/capacity_load_test_readiness_plan.py`
- 测试：
  - `tests/test_sre_observability_baseline_v381.py`
  - `tests/test_slo_alerting_runbook_pack_v382.py`
  - `tests/test_backup_restore_dr_evidence_pack_v383.py`
  - `tests/test_capacity_load_test_readiness_plan_v384.py`
- 版本同步：
  - `pyproject.toml`
  - `app/main.py`
  - `app/tools/mcp/stdio_client.py`
  - 相关版本断言测试

## Verification Matrix

| 验证项 | 命令 | 结果 |
|---|---|---|
| Phase 18.1 | `python -m pytest tests/test_sre_observability_baseline_v381.py -q` | passed |
| Phase 18.2 | `python -m pytest tests/test_slo_alerting_runbook_pack_v382.py -q` | passed |
| Phase 18.3 | `python -m pytest tests/test_backup_restore_dr_evidence_pack_v383.py -q` | passed |
| Phase 18.4 | `python -m pytest tests/test_capacity_load_test_readiness_plan_v384.py -q` | passed |
| v3.8 关联回归 | `python -m pytest tests/test_sre_observability_baseline_v381.py tests/test_slo_alerting_runbook_pack_v382.py tests/test_backup_restore_dr_evidence_pack_v383.py tests/test_capacity_load_test_readiness_plan_v384.py tests/test_runtime_persistence_v05.py tests/test_runtime_hardening_v055.py tests/test_operations_summary_v312.py tests/test_failure_diagnostics_v324.py tests/test_request_guards_v72.py -q` | passed |
| 全量回归 | `python -m pytest -q` | 900 passed, 4 skipped, 2 warnings |
| Diff 检查 | `git diff --check` | passed，仅 CRLF 提示 |

## Security And Privacy

- 所有新增脚本只输出 env name 与 present 布尔状态，不读取或输出真实 secret 原文。
- 默认不连接真实外部系统，不调用真实 LLM，不执行真实 MCP。
- 默认不发告警，不通知 on-call，不执行压测、备份恢复、DR failover 或 migration。
- `skipped` 语义保留，缺少 opt-in 或演练证据不得伪造成 `success`。

## Operational Boundary

- 当前交付是 SRE 接管前的只读证据基线，不是企业级 APM/告警/DR/容量验收完成。
- 当前仍不宣称公网生产可直接上线。
- 当前仍不宣称真实 LLM 生产验收、生产级 SSO/OIDC、多租户或复杂 BI 完成。
- 本轮 release prep 不打 tag、不创建 GitHub Release、不移动历史 tag。

## Go/No-Go

- Go：可以进入 `v3.8.0` tag 前最终复核，并继续准备真实 APM/告警、备份恢复、DR 和压测演练。
- No-Go：不得把本轮只读 runbook 与 `skipped/partial` 结果当作生产 SRE、RTO/RPO、DR 或容量验收成功。

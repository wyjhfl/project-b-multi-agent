# v3.8 SRE observability baseline（只读）

Phase 18.1 建立 SRE 观测基线，用于在引入企业级 APM、集中日志、告警和值班体系前，确认当前项目已有的本地观测、诊断和 runbook 证据，以及仍需补齐的生产验收缺口。

## 交付物

- 只读脚本：`scripts/sre_observability_baseline.py`
- 测试：`tests/test_sre_observability_baseline_v381.py`
- 默认输出目录：`docs/reports/sre_observability_baseline/`
- 输出格式：JSON + Markdown

## 检查范围

- Runtime metrics 与 cost API：`/metrics/runtime`、cost/tools/tasks summary、RuntimeMetricsRecorder、SQLite/PostgreSQL MetricsStore。
- Runtime snapshot：`/runtime/snapshot` 的本地代码与回归测试。
- Operations summary 与验收证据：`/operations/summary`、acceptance snapshot、demo artifact bundle。
- Audit export 与 redaction：audit API、SQLite/PostgreSQL AuditStore、audit retention/export 测试。
- Structured logging：结构化日志、请求日志、脱敏边界。
- Failure diagnostics：failure diagnostics 脚本、runbook 和测试。
- Backup/restore 与 DR runbook：备份恢复清单、运维排障索引、监控备份演练记录、部署 runbook。
- APM/Tracing、告警、SLO/SLI、on-call、容量压测、备份恢复和 DR 切换缺口。

## 边界

- 不启动服务。
- 不访问在线 `/health`、`/metrics`、`/operations` 或 `/runtime/snapshot` 端点。
- 不连接真实 APM、日志平台、告警平台或值班系统。
- 不执行真实压测、备份恢复或灾备切换。
- 不删除用户数据，不自动清理报告，不修改 `.env`。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码或告警 webhook 原文。
- 不把本地 metrics store、只读脚本或 runbook 视为企业级 SRE 验收完成。

## 运行方式

```powershell
python scripts/sre_observability_baseline.py
```

指定输出目录：

```powershell
python scripts/sre_observability_baseline.py --output-dir docs/reports/sre_observability_baseline
```

## 状态语义

- `skipped`：缺少真实 SRE opt-in、APM、告警、容量、备份恢复、DR 或 RTO/RPO 证据。
- `partial`：本地观测与 runbook 证据存在，但仍不代表企业级 SRE 验收完成。
- `blocked`：输出中检测到 secret-like 文本或出现不可接受边界风险。
- `failed`：脚本运行异常或输出无法生成。
- `success`：保留状态词，不用于默认离线基线伪造成生产成功。

## 推荐回归

```powershell
python -m pytest tests/test_sre_observability_baseline_v381.py -q
python -m pytest tests/test_runtime_persistence_v05.py tests/test_runtime_hardening_v055.py tests/test_operations_summary_v312.py tests/test_audit_v045.py tests/test_audit_retention_export_v74.py tests/test_failure_diagnostics_v324.py -q
python scripts/sre_observability_baseline.py
```

## Go / No-Go 口径

- Go：可进入 SLO/SLI、告警、on-call、备份恢复、DR 和容量压测的 runbook 与受控演练准备。
- No-Go：把本地 metrics store 等同于企业级 APM、把 runbook 当作真实 RTO/RPO 达成证据、触发真实告警、执行真实压测或恢复、输出 secret 原文，或把 `skipped/partial` 伪造成生产成功。

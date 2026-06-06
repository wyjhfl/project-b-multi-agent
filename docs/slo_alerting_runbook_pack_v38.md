# v3.8 SLO/SLI and alerting runbook pack（只读）

## 目标

建立 SLO/SLI 与告警 runbook 包，明确当前可作为 SLI 来源的本地 metrics、runtime snapshot、operations summary、structured logging 和 failure diagnostics 证据，同时标记真实告警、on-call、升级演练和错误预算管理缺口。

## 交付物

- 只读脚本：`scripts/slo_alerting_runbook_pack.py`
- 测试：`tests/test_slo_alerting_runbook_pack_v382.py`
- 默认输出目录：`docs/reports/slo_alerting_runbook/`
- 输出格式：JSON + Markdown

## 覆盖范围

- SLO/SLI 指标来源盘点：runtime metrics、runtime snapshot、operations summary。
- SLO 目标配置盘点：availability、latency p95、error-rate。
- 告警上下文：structured logging、request logging、failure diagnostics。
- 告警分级与路由：P0/P1/P2、alert channel、escalation policy。
- on-call 与升级：值班轮转、升级路径、演练报告缺口。
- dry-run 证据：不触发真实 webhook，仅记录 dry-run 报告是否缺失。
- regression evidence：metrics、operations、failure diagnostics、SRE baseline 相关测试存在性。

## 默认边界

- 不启动服务。
- 不访问在线 `/health`、`/metrics`、`/operations` 或 `/runtime/snapshot` 端点。
- 不连接真实 APM、日志平台、告警平台或值班系统。
- 不发送真实告警，不通知真实 on-call，不执行真实 incident 升级。
- 不执行真实压测、备份恢复或灾备切换。
- 不修改 `.env`，不删除用户数据，不自动清理报告。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码或告警 webhook 原文。
- 不把 runbook、placeholder env 或本地 metrics store 宣称为企业级 SLO/告警验收完成。

## 使用方式

```powershell
python scripts/slo_alerting_runbook_pack.py
```

指定输出目录：

```powershell
python scripts/slo_alerting_runbook_pack.py --output-dir docs/reports/slo_alerting_runbook
```

## 验证

```powershell
python -m pytest tests/test_slo_alerting_runbook_pack_v382.py -q
python scripts/slo_alerting_runbook_pack.py --output-dir docs/reports/slo_alerting_runbook
```

## Go/No-Go

- Go：可以作为 SLO/SLI 和告警 runbook 的只读基线，进入人工确认 SLO 目标、真实告警 dry-run 和 on-call 升级演练准备。
- No-Go：不得把 `skipped/partial` 当作真实告警验收成功；不得在没有真实 dry-run 和 on-call 证据前宣称 SLO/告警生产验收完成；不得输出真实 secret 原文。

# v3.8 capacity and load-test readiness plan（只读）

## 目标

建立容量与压测准备计划，明确企业内网试点需要的流量模型、关键 API 覆盖、请求防护、可观测性、压测 dry-run、soak test 和报告证据缺口。

## 交付物

- 只读脚本：`scripts/capacity_load_test_readiness_plan.py`
- 测试：`tests/test_capacity_load_test_readiness_plan_v384.py`
- 默认输出目录：`docs/reports/capacity_load_test_readiness/`
- 输出格式：JSON + Markdown

## 覆盖范围

- 关键 API 入口盘点：health、metrics、runtime snapshot、operations、tasks、tools、NL2SQL、approvals。
- 流量模型目标：并发、RPS、p95 延迟、错误率、测试时长。
- 请求防护：request size limit、rate limit、abuse guard。
- 可观测性：structured logging、runtime metrics、failure diagnostics。
- 压测 dry-run 证据：缺少计划或报告时保持 `skipped`。
- soak test 证据：缺少报告时保持 `skipped`。
- runbook 串联：deployment、SRE baseline、SLO/alerting、backup/DR。

## 默认边界

- 不启动服务，不访问在线端点。
- 不执行真实压测、soak test、并发请求或容量探测。
- 不连接真实 PostgreSQL、Redis、APM、日志平台、告警平台、IdP、LLM provider、外部 MCP 或业务系统。
- 不写业务数据、审计数据或指标数据。
- 不删除用户数据，不清理报告，不修改 `.env`。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码或压测目标 URL 原文。
- 不把 runbook、placeholder env 或本地测试通过宣称为生产容量上限验收完成。

## 使用方式

```powershell
python scripts/capacity_load_test_readiness_plan.py
```

指定输出目录：

```powershell
python scripts/capacity_load_test_readiness_plan.py --output-dir docs/reports/capacity_load_test_readiness
```

## 验证

```powershell
python -m pytest tests/test_capacity_load_test_readiness_plan_v384.py -q
python scripts/capacity_load_test_readiness_plan.py --output-dir docs/reports/capacity_load_test_readiness
```

## Go/No-Go

- Go：可以作为容量与压测准备的只读基线，进入真实压测 dry-run、soak test、指标采集和告警阈值确认。
- No-Go：不得把 `skipped/partial` 当作真实容量验收成功；不得在没有真实压测和长期稳定性报告前宣称生产容量上限已确认；不得输出真实 secret 原文。

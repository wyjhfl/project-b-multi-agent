# v4.0 Phase 20.3 Production Runbook Finalization Runbook

## 目标

本 runbook 用于生成生产上线前操作手册索引，汇总部署、回滚、incident、DR、密钥轮换、审计导出、SLO/告警、容量、Launch Readiness 和 blocker register 的本地证据入口。

该索引用于人工复核生产 runbook 完整性，不启动服务，不执行部署或回滚，不触发告警，不读取 `.env` 或 secret，不代表生产 Go。

## 默认命令

```powershell
python scripts/production_runbook_finalization.py
```

默认输出目录：

```text
docs/reports/production_runbook_finalization/
```

可选串联 Phase 20.1/20.2 JSON：

```powershell
python scripts/production_runbook_finalization.py `
  --launch-readiness docs/reports/production_launch_readiness/<review>.json `
  --launch-blockers docs/reports/launch_blockers/<register>.json `
  --output-dir docs/reports/production_runbook_finalization
```

## 状态语义

- `success`：保留给未来所有必需 runbook 入口存在、上游输入可解释且无未关闭 blocker 的扩展场景；当前默认不自动生成生产 Go。
- `partial`：部分 runbook 入口存在，但仍有缺失项、未关闭 blocker 或需要人工复核。
- `skipped`：关键输入缺失或本地 runbook 入口不足，必须保留缺失条件。
- `blocked`：发现 secret-like 输入、非只读输入、意外真实外部执行、自动批准/关闭、上游 `blocked/failed` 或边界违规。
- `failed`：脚本执行异常或输出不可用。

## 覆盖范围

- 部署：deployment runbook、prod smoke/down 脚本、Docker/compose 配置。
- 回滚：release gate / rollback governance、部署演练与回滚记录。
- Incident：incident rehearsal、failure diagnostics、operations troubleshooting。
- DR：backup/restore checklist、backup/restore DR evidence pack、operations monitoring backup drill。
- 密钥轮换：secret rotation and leakage response pack、OIDC lifecycle drill。
- 审计导出：audit retention/export、security regression evidence、cross-tenant audit evidence。
- SLO/告警：SLO/SLI and alerting runbook pack、SRE observability baseline。
- 容量：capacity and load-test readiness plan。
- 上线评审：Production Launch Readiness Review、Launch Blocker Register。

## 只读边界

- 默认 fake/offline。
- 不启动服务，不访问在线端点。
- 不连接真实 IdP、LLM provider、外部 MCP、业务系统、PostgreSQL、Redis、APM、日志、告警、KMS、Vault、对象存储或云平台。
- 不读取 `.env` 或真实 secret 值。
- 不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、红队测试、审计导出、密钥轮换或权限变更。
- 不发送真实告警，不通知真实 on-call，不调用真实 webhook。
- 不写业务数据，不修改上游报告，不移动、删除、重建历史 tag。
- 不自动批准上线，不自动关闭 blocker，不创建 GitHub Release。

## Go/No-Go 口径

- 公网生产直上：No-Go。
- 企业内网受控试点评审：可继续人工复核。
- 最终生产 Go：需要人工确认所有 runbook 入口、演练证据、责任人、到期时间、补偿控制和关闭证据。

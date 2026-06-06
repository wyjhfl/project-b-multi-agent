# v3.8 backup/restore and DR drill evidence pack（只读）

## 目标

建立备份恢复与灾备演练证据包，明确 PostgreSQL、SQLite demo、审计、指标、报告和配置模板的备份范围，以及 RTO/RPO、恢复 dry-run、DR 切换和失败回滚证据缺口。

## 交付物

- 只读脚本：`scripts/backup_restore_dr_evidence_pack.py`
- 测试：`tests/test_backup_restore_dr_evidence_pack_v383.py`
- 默认输出目录：`docs/reports/backup_restore_dr_evidence/`
- 输出格式：JSON + Markdown

## 覆盖范围

- 备份范围盘点：SQLite demo、SQLite/PostgreSQL audit store、metrics store、task store。
- 部署与迁移边界：Alembic、compose、deployment guard。
- RTO/RPO 配置：仅记录 env name 与 present 布尔状态。
- 备份演练证据：缺少真实演练报告时保持 `skipped`。
- 恢复 dry-run 证据：缺少真实恢复报告时保持 `skipped`。
- DR 切换证据：缺少真实 DR failover 报告时保持 `skipped`。
- runbook 串联：backup/restore checklist、operations drill、deployment runbook、failure diagnostics。

## 默认边界

- 不启动服务。
- 不连接真实 PostgreSQL、Redis、对象存储、IdP、LLM provider 或外部 MCP。
- 不执行真实备份，不执行真实恢复，不执行灾备切换。
- 不执行 Alembic migration，不写业务数据、审计数据或指标数据。
- 不删除用户数据，不移动或清理报告，不修改 `.env`。
- 不读取或输出真实 secret、token、API key、client_secret、`DATABASE_URL`、`REDIS_URL` 或对象存储凭证原文。
- 不把 runbook、placeholder env 或本地 SQLite 文件宣称为 RTO/RPO 或 DR 生产验收完成。

## 使用方式

```powershell
python scripts/backup_restore_dr_evidence_pack.py
```

指定输出目录：

```powershell
python scripts/backup_restore_dr_evidence_pack.py --output-dir docs/reports/backup_restore_dr_evidence
```

## 验证

```powershell
python -m pytest tests/test_backup_restore_dr_evidence_pack_v383.py -q
python scripts/backup_restore_dr_evidence_pack.py --output-dir docs/reports/backup_restore_dr_evidence
```

## Go/No-Go

- Go：可以作为备份恢复与 DR 演练的只读证据基线，进入真实备份、恢复 dry-run、DR failover 和 RTO/RPO 达成证据准备。
- No-Go：不得把 runbook 或 `skipped/partial` 当作真实备份恢复成功；不得在没有真实恢复和 DR 演练证据前宣称 RTO/RPO 或生产 DR 验收完成；不得输出真实 secret 原文。

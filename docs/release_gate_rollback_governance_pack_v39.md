# v3.9 release gate and rollback governance pack（只读）

## 目标

建立发布门禁与回滚治理证据包，盘点 deployment guard、compose、Alembic、release notes、release review、变更审批、发布签核、回滚演练、治理例外和安全合规串联证据缺口。

## 交付物

- 只读脚本：`scripts/release_gate_rollback_governance_pack.py`
- 测试：`tests/test_release_gate_rollback_governance_pack_v393.py`
- 默认输出目录：`docs/reports/release_gate_rollback_governance/`
- 输出格式：JSON + Markdown

## 覆盖范围

- 部署门禁：deployment guard、deployment API、deployment runbook、production readiness checklist。
- 发布产物：pyproject、release notes、release review、security Go/No-Go。
- 部署与迁移预检：compose、prod override、Dockerfile、Alembic。
- 变更审批：发布审批记录、冻结窗口、发布负责人。
- 发布签核：配置预检、迁移预检、测试门禁、安全复核、合规签核。
- 回滚演练：rollback drill、backup/DR runbook、failure diagnostics、evidence archive。
- 治理串联：compliance baseline、secret rotation、release review。

## 默认边界

- 不启动服务，不访问在线端点。
- 不执行 git tag、GitHub Release、部署、迁移、回滚、数据恢复或外部系统调用。
- 不连接真实 PostgreSQL、Redis、IdP、LLM provider、外部 MCP、业务系统、APM、日志平台或告警平台。
- 不写业务数据、审计数据、指标数据或配置文件。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- 不把 release notes、release review、runbook 或配置模板宣称为生产发布门禁或回滚验收完成。

## 使用方式

```powershell
python scripts/release_gate_rollback_governance_pack.py
```

指定输出目录：

```powershell
python scripts/release_gate_rollback_governance_pack.py --output-dir docs/reports/release_gate_rollback_governance
```

## 验证

```powershell
python -m pytest tests/test_release_gate_rollback_governance_pack_v393.py -q
python scripts/release_gate_rollback_governance_pack.py --output-dir docs/reports/release_gate_rollback_governance
```

## Go/No-Go

- Go：可以作为发布门禁与回滚治理的只读基线，进入真实变更审批、发布签核和回滚演练证据准备。
- No-Go：不得把 release review、runbook 或 `skipped/partial` 当作生产发布批准；不得执行真实发布、tag、Release、migration 或回滚；不得输出真实 secret 原文。

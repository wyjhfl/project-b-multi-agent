# v4.0 Production Launch Readiness Review Runbook

## 目标

本 runbook 用于生成生产上线前只读评审包，汇总 v3.5~v3.9 的试点收口、证据归档、真实 provider 验收、SRE/DR、容量、安全合规、发布门禁和回滚治理证据。

## 默认命令

```powershell
python scripts/production_launch_readiness_review.py
```

默认输出目录：

```text
docs/reports/production_launch_readiness/
```

可选传入既有 JSON 报告：

```powershell
python scripts/production_launch_readiness_review.py `
  --evidence-archive docs/reports/evidence_archive/<manifest>.json `
  --pilot-closeout docs/reports/pilot_closeout/<report>.json `
  --compliance-baseline docs/reports/compliance_security_baseline/<report>.json `
  --release-gate docs/reports/release_gate_rollback_governance/<report>.json `
  --security-regression docs/reports/security_regression_compliance_evidence/<report>.json
```

## 输出

- JSON：结构化评审结果、阻断项、缺失条件、证据入口、边界声明。脚本仅消费传入 JSON 的结构化字段，不读取 Markdown 报告正文。
- Markdown：人工审阅摘要、Go/No-Go 建议、下一步动作。

## 状态语义

- `success`：仅表示输入元数据完整且未发现脚本级阻断，不等于生产 Go。
- `partial`：存在缺失证据、未完成验收或需要人工复核。
- `blocked`：发现 secret-like 内容、意外真实外部执行标记或关键输入违反只读边界。
- `skipped`：提供了输入但路径不存在、无法解析、全部来源为 skipped，或本地证据入口缺失。
- `failed`：脚本执行异常。

## 边界

- 默认 fake/offline。
- 不启动服务，不访问在线端点。
- 不连接真实 IdP、LLM provider、外部 MCP、业务系统、PostgreSQL、Redis、APM、日志、告警、KMS、Vault、对象存储或云平台。
- 不读取 `.env` 或真实 secret 值。
- 不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、红队测试、审计导出、密钥轮换或权限变更。
- 不把 `skipped`、`blocked`、`partial` 或只读本地证据汇总伪造成生产上线批准。

## Go/No-Go 口径

- 企业内网受控试点评审可继续。
- 公网生产直上为 No-Go。
- 若真实 SSO/OIDC、租户隔离、真实 LLM、真实 MCP、业务系统集成、SRE/DR、容量、安全合规、发布门禁或回滚演练存在未关闭阻断项，则生产上线为 No-Go。
- 最终 Go 需要人工签核、责任人、到期时间、补偿控制和关闭证据。

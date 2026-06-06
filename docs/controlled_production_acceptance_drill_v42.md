# v4.2 Controlled Production Acceptance Drill（只读）

## 定位

本阶段建立受控生产验收演练包，用于汇总真实生产验收前需要人工复核的脱敏证据。脚本只消费结构化 JSON 字段，不连接真实外部系统，不执行真实验收动作。

## 覆盖域

- real LLM
- OIDC / SSO
- external MCP
- PostgreSQL
- Redis
- business system
- APM / logging / alerting
- backup / restore / DR
- capacity / load / soak
- security / compliance
- release / rollback gate

## 输入与输出

- 输入：脱敏 acceptance evidence JSON。
- 默认输出目录：`docs/reports/controlled_production_acceptance/`。
- 输出格式：JSON + Markdown。

## 状态语义

- `skipped`：未提供验收证据、输入不可读取或上游显式 skipped。
- `partial`：已生成受控验收演练包，可进入人工复核；不表示生产验收完成。
- `blocked`：上游 blocked/failed、检测到 secret-like 输入、非只读输入、真实执行或连接标记、自动审批/自动关闭标记、release/tag 标记。

本阶段不主动输出 `success`，避免把脱敏证据汇总误读为真实生产验收完成。

## 只读边界

- 不读取 Markdown 报告正文。
- 不读取或输出真实 secret 原文。
- 不连接真实 LLM、IdP、MCP、PostgreSQL、Redis、业务系统、APM、日志、告警、KMS、Vault、对象存储或云平台。
- 不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、审计导出、密钥轮换或权限变更。
- 不自动批准上线，不自动关闭 blocker，不创建 GitHub Release，不打 tag。

## 验收命令

```powershell
pytest tests/test_controlled_production_acceptance_drill_v421.py
```

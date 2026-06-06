# v3.9 security regression and compliance evidence pack（只读）

## 目标

建立安全回归与合规证据包，盘点 prompt injection、PII 泄漏、SQL guard、边界防护、越权访问、跨租户拒绝、审计导出脱敏、发布门禁和合规证据串联缺口。

## 交付物

- 只读脚本：`scripts/security_regression_compliance_evidence_pack.py`
- 测试：`tests/test_security_regression_compliance_evidence_pack_v394.py`
- 默认输出目录：`docs/reports/security_regression_compliance_evidence/`
- 输出格式：JSON + Markdown

## 覆盖范围

- Prompt injection：InjectionGuard、RiskIntentGuard、Guardrails。
- PII 与脱敏：PIIGuard、structured logging。
- SQL 安全：SQLGuard 与安全测试。
- 边界防护：security headers、request guards、rate limit、abuse guard。
- 身份与权限：auth、RBAC、permission matrix。
- 跨租户拒绝：cross-tenant audit evidence。
- 审计导出：audit API、retention、redaction。
- 发布门禁串联：release gate governance。
- 合规证据串联：compliance baseline、secret rotation、security Go/No-Go。

## 默认边界

- 不启动服务，不访问在线端点。
- 不执行真实 SAST、DAST、依赖扫描、红队测试、外部审计或外部系统调用。
- 不连接真实 IdP、LLM provider、外部 MCP、业务系统、数据库、Redis、APM、日志平台或告警平台。
- 不修改用户、角色、权限、租户、业务数据、审计数据、指标数据或配置文件。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- 不把本地测试存在性、runbook 或只读证据索引宣称为企业级安全合规验收完成。

## 使用方式

```powershell
python scripts/security_regression_compliance_evidence_pack.py
```

指定输出目录：

```powershell
python scripts/security_regression_compliance_evidence_pack.py --output-dir docs/reports/security_regression_compliance_evidence
```

## 验证

```powershell
python -m pytest tests/test_security_regression_compliance_evidence_pack_v394.py -q
python scripts/security_regression_compliance_evidence_pack.py --output-dir docs/reports/security_regression_compliance_evidence
```

## Go/No-Go

- Go：可以作为安全回归与合规证据的只读基线，进入外部扫描、红队测试、正式安全签核和 release gate 串联准备。
- No-Go：不得把本地测试存在性或 `skipped/partial` 当作企业级安全合规验收成功；不得执行真实外部扫描或输出真实 secret 原文。

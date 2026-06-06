# v3.9 compliance security baseline inventory（只读）

## 目标

建立合规安全基线盘点，明确 deployment guard、安全响应头、request guard、结构化日志脱敏、审计留存与导出、RBAC、OIDC、prompt injection、PII guard、跨租户审计和 release review 的现有证据与缺口。

## 交付物

- 只读脚本：`scripts/compliance_security_baseline.py`
- 测试：`tests/test_compliance_security_baseline_v391.py`
- 默认输出目录：`docs/reports/compliance_security_baseline/`
- 输出格式：JSON + Markdown

## 覆盖范围

- 部署门禁与发布边界：deployment guard、deployment runbook、release review。
- 安全响应头与请求防护：security headers、request size limit、rate limit、abuse guard。
- 审计、日志、留存与脱敏：audit API/store、retention、structured logging。
- 身份、RBAC 与 OIDC：auth、JWT、RBAC、OIDC 最小骨架和测试。
- 权限与跨租户证据：RBAC matrix、cross-tenant audit evidence。
- Prompt/PII 安全：injection guard、risk intent guard、guardrails、PII guard。
- 合规文档：security Go/No-Go、production security baseline、audit log plan。
- 正式签核与密钥轮换缺口：缺少 opt-in 或演练证据时保持 `skipped`。

## 默认边界

- 不启动服务，不访问在线端点。
- 不连接真实 IdP、APM、日志平台、告警平台、对象存储、PostgreSQL、Redis、外部 MCP 或业务系统。
- 不执行真实安全扫描、真实审计导出、真实密钥轮换、真实权限变更、真实发布或真实回滚。
- 不修改用户、角色、权限、租户、业务数据、审计数据或指标数据。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码、告警 webhook 或生产 URL 原文。
- 不把配置模板、只读脚本或 runbook 宣称为企业级合规、安全治理或发布门禁验收完成。

## 使用方式

```powershell
python scripts/compliance_security_baseline.py
```

指定输出目录：

```powershell
python scripts/compliance_security_baseline.py --output-dir docs/reports/compliance_security_baseline
```

## 验证

```powershell
python -m pytest tests/test_compliance_security_baseline_v391.py -q
python scripts/compliance_security_baseline.py --output-dir docs/reports/compliance_security_baseline
```

## Go/No-Go

- Go：可以作为 v3.9 合规安全加固的只读基线，进入密钥轮换、发布门禁、回滚治理和安全回归证据包准备。
- No-Go：不得把配置模板或 `skipped/partial` 当作合规安全验收成功；不得在缺少正式签核、密钥轮换和发布门禁证据前宣称企业级合规完成；不得输出真实 secret 原文。

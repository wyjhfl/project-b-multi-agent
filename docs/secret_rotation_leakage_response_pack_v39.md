# v3.9 secret rotation and leakage response pack（只读）

## 目标

建立密钥轮换与泄漏响应证据包，盘点 JWT、OIDC、数据库、Redis、LLM、MCP、业务系统和告警 webhook 等 secret surface 的治理边界、轮换证据、撤销恢复证据和泄漏响应缺口。

## 交付物

- 只读脚本：`scripts/secret_rotation_leakage_response_pack.py`
- 测试：`tests/test_secret_rotation_leakage_response_pack_v392.py`
- 默认输出目录：`docs/reports/secret_rotation_leakage_response/`
- 输出格式：JSON + Markdown

## 覆盖范围

- Secret surface：`JWT_SECRET`、`DATABASE_URL`、`REDIS_URL`、`OIDC_CLIENT_SECRET`、真实 LLM key env、MCP command、业务系统 key env、告警 webhook。
- 脱敏与审计边界：structured logging、audit API/store、audit retention。
- 身份密钥生命周期：JWT、OIDC lifecycle drill、IdP client secret。
- 外部集成密钥边界：optional integration readiness、controlled integration dry-run。
- 治理例外串联：governance exception register、compliance baseline。
- 轮换、泄漏响应、撤销恢复演练证据缺口。

## 默认边界

- 不读取 `.env` 或任何真实 secret 值。
- 不连接真实 KMS、Vault、云平台、IdP、LLM provider、外部 MCP、数据库、Redis、告警平台或业务系统。
- 不执行真实密钥创建、轮换、撤销、禁用、泄漏扫描或告警通知。
- 不修改用户、角色、权限、租户、业务数据、审计数据、指标数据或配置文件。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- 不把配置模板、env name、只读脚本或 runbook 宣称为企业级密钥治理完成。

## 使用方式

```powershell
python scripts/secret_rotation_leakage_response_pack.py
```

指定输出目录：

```powershell
python scripts/secret_rotation_leakage_response_pack.py --output-dir docs/reports/secret_rotation_leakage_response
```

## 验证

```powershell
python -m pytest tests/test_secret_rotation_leakage_response_pack_v392.py -q
python scripts/secret_rotation_leakage_response_pack.py --output-dir docs/reports/secret_rotation_leakage_response
```

## Go/No-Go

- Go：可以作为密钥治理的只读基线，进入真实轮换窗口、泄漏响应、撤销恢复和审计证据准备。
- No-Go：不得把 env name、配置模板或 `skipped/partial` 当作真实密钥治理完成；不得执行真实轮换或泄漏扫描；不得输出真实 secret 原文。

# 演示业务只读接口准备说明

## 目标

当前没有真实 CRM、ERP、订单中心或其他业务系统时，可以先使用 `scripts/production_landing_demo_business_smoke.py` 启动一个受控演示业务只读服务，验证 Project B 的业务系统接入链路、鉴权、ToolGateway、PolicyEngine 和脱敏报告生成。

该路径只用于内网试点演示和本地落地验证，不等同于真实业务系统生产验收。报告会写入 `demo_business_system_used=true`，下游 readiness 与 landing execution pack 会继续保留真实业务系统缺口。

## 演示接口

- Method: `GET`
- Path: `/health`
- 默认 base URL: `http://127.0.0.1:8876`
- 默认鉴权: `Authorization: Bearer <read-only-token>`
- 写方法: `POST`、`PUT`、`PATCH`、`DELETE` 均返回 405
- 演示只读凭据只允许写入 ignored 的本地 env 文件或通过交互提示输入；文档和仓库不记录真实值。

成功响应示例：

```json
{
  "status": "ok",
  "system": "demo_business_system",
  "environment": "controlled-demo",
  "readonly": true
}
```

## 本地配置

`local/production_landing.staging.env` 是 ignored 本地文件，可配置：

```text
BUSINESS_INTEGRATION_ENABLED=true
BUSINESS_INTEGRATION_READ_ONLY=true
BUSINESS_INTEGRATION_WRITE_ENABLED=false
BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true
BUSINESS_INTEGRATION_AUDIT_REQUIRED=true
BUSINESS_SYSTEM_NAME=demo_business_system
BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL
BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN
BUSINESS_SYSTEM_BASE_URL=http://127.0.0.1:8876
BUSINESS_SYSTEM_TOKEN=secret-managed-token
BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe
BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=
BUSINESS_SYSTEM_TIMEOUT_SECONDS=5
BUSINESS_SYSTEM_READ_PROBE_PATH=/health
BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization
BUSINESS_SYSTEM_AUTH_SCHEME=Bearer
```

## 执行

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\production_landing_demo_business_smoke.py --env-path local\production_landing.staging.env
```

或通过受控 runner：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\production_landing_env_runner.py --action demo-business-smoke --env-path local\production_landing.staging.env
```

## 替换为真实业务系统

拿到真实业务系统后，将本地配置替换为真实系统名、真实 base URL、真实只读凭据和只读探测路径。真实凭据不要写入仓库，不要发到聊天或报告中，优先通过 `scripts/business_system_read_smoke.ps1` 的交互式安全提示输入。

真实业务系统验收必须满足：

- `demo_business_system_used=false`
- `local_business_mock_used=false`
- `business_system_connected=true`
- `business_read_executed=true`
- `business_write_executed=false`
- `business_data_written=false`
- `secret_plaintext_output=false`

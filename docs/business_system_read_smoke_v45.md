# v4.5 业务系统只读 Smoke

## 定位

`scripts/business_system_read_smoke.py` 是真实业务系统只读探测入口。默认不执行真实连接；只有显式 `--execute` 且环境变量满足 opt-in 时，才通过 `ToolGateway`、`PolicyEngine` 和 `business_read_probe` 读取健康或探测接口。

该 smoke 用于补齐真实业务系统 read-only evidence。它不代表公网生产直上，`public_production_direct_launch` 必须保持 `No-Go`。

## 生成环境模板

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\business_system_read_smoke.py --write-env-template docs\reports\business_system_read_smoke\business_read_smoke.env.template
```

模板只包含占位值。真实 `BUSINESS_SYSTEM_BASE_URL` 和 `BUSINESS_SYSTEM_TOKEN` 只能放在本地 `.env`、当前进程环境或外部 secret manager 中，不得提交到仓库。

## 必要环境变量

- `BUSINESS_INTEGRATION_ENABLED=true`
- `BUSINESS_INTEGRATION_READ_ONLY=true`
- `BUSINESS_INTEGRATION_WRITE_ENABLED=false`
- `BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true`
- `BUSINESS_INTEGRATION_AUDIT_REQUIRED=true`
- `BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL`
- `BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN`
- `BUSINESS_SYSTEM_BASE_URL=<真实业务系统 URL>`
- `BUSINESS_SYSTEM_TOKEN=<真实只读 token>`
- `BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe`
- `BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=`
- `BUSINESS_SYSTEM_READ_PROBE_PATH=/health`
- `BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization`
- `BUSINESS_SYSTEM_AUTH_SCHEME=Bearer`
- `BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>`
- `BUSINESS_SYSTEM_SECURITY_REVIEWER=<owner-or-staff-id>`
- `BUSINESS_SYSTEM_OPERATIONS_OWNER=<owner-or-staff-id>`
- `BUSINESS_SYSTEM_DATA_OWNER=<owner-or-staff-id>`

如果业务系统使用 API Key header，可设置 `BUSINESS_SYSTEM_AUTH_HEADER_NAME=X-API-Key` 与 `BUSINESS_SYSTEM_AUTH_SCHEME=`；脚本只输出 header 名和 scheme 是否配置，不输出 token 原文。

## 执行只读 Smoke

推荐使用 PowerShell 安全入口。该入口只把业务系统 URL/token 注入当前进程环境，执行结束后恢复环境；不会写入 `.env`、仓库、命令行参数或报告正文：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\business_system_read_smoke.ps1
```

自定义鉴权头示例：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\business_system_read_smoke.ps1 -AuthHeaderName X-API-Key -AuthScheme ""
```

如已由外部 secret manager 注入 `BUSINESS_SYSTEM_BASE_URL` 与 `BUSINESS_SYSTEM_TOKEN`，可使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\business_system_read_smoke.ps1 -UseExistingEnv -BusinessOwner WYJ -SecurityReviewer WYJ -OperationsOwner WYJ -DataOwner WYJ
```

如需要从本地 ignored env 文件加载非密钥配置和 owner，可使用 `-EnvPath`。该入口会跳过 `BUSINESS_SYSTEM_BASE_URL`、`BUSINESS_SYSTEM_TOKEN`、`DATABASE_URL`、`REDIS_URL`、`XIAOMI_LLM_API_KEY`、`JWT_SECRET`，真实 URL/token 仍必须来自当前进程环境、外部 secret manager 或交互式输入：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\business_system_read_smoke.ps1 -EnvPath local\production_landing.staging.env
```

自动化环境仍可使用 Python 入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\business_system_read_smoke.py --execute
```

成功后输出 `business_system_connected=true`、`business_read_executed=true`、`business_write_executed=false`、`business_data_written=false`，并生成脱敏 JSON/Markdown 报告。

通过本地 mock 入口生成证据时，报告必须带有 `local_business_mock_used=true`；真实业务系统验收必须满足 `local_business_mock_used=false`。通过 SSH tunnel、反向代理或 port-forward 暴露到 `localhost` 的真实业务系统不会被自动判为 local mock；只有显式设置 `BUSINESS_SYSTEM_NAME=local_business_read_mock` 或运行 `local-business-smoke` 才会标记 local mock。

## 输入准备包

在提供真实业务系统信息前，可先生成只读输入准备包：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\business_system_input_packet.py
```

该脚本只检查环境变量是否存在，不读取或输出 URL/token 原文。输出会列出缺口、推荐命令、owner 字段和安全边界。

## 边界

- 不执行业务写入。
- 不绕过 `ToolGateway`、`PolicyEngine`、审批或审计边界。
- 不输出 token、base URL、连接串或其他 secret 原文。
- 成功只代表只读 smoke 证据进入人工复核，不代表公网生产可直接上线。

## PowerShell 安全入口补充

`scripts\business_system_read_smoke.ps1` 会在执行只读 smoke 后自动生成 `business_system_production_readiness` brief。该入口会要求提供 `business_owner`、`security_reviewer`、`operations_owner`、`data_owner`，这些 owner 只注入当前进程环境，用于证明真实业务系统接入责任边界；不得填写 token、连接串或其他 secret。

非交互负责人示例：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\business_system_read_smoke.ps1 -BusinessOwner WYJ -SecurityReviewer WYJ -OperationsOwner WYJ -DataOwner WYJ
```

如仅需执行 smoke 而暂不生成 readiness brief，可显式追加 `-SkipReadinessBrief`。生产试点验收不建议跳过。

# 受控内网试点运行包

## 目标

`scripts/controlled_pilot_run_packet.py` 用于把当前受控内网试点的关键证据收敛成一份只读运行包。它面向操作员和技术负责人，回答三个问题：

- 当前是否可以进入受控内网试点窗口。
- 当前仍有哪些不能用于真实生产验收的缺口。
- 操作员应该使用哪些命令刷新、验证和回滚本地试点控制台。

该运行包只代表 `controlled_internal_pilot`，不代表公网生产可直接上线。

## 默认边界

- 只读取 `docs/reports/` 下的结构化 JSON 证据。
- 不连接真实业务系统、PostgreSQL、Redis 或外部 MCP。
- 不调用真实 LLM。
- 不执行 Alembic migration。
- 不写业务数据、审计数据或指标数据。
- 不读取或输出 API key、token、连接串、密码等 secret 原文。
- `public_production_direct_launch` 始终必须保持 `No-Go`。

## 输入证据

默认读取以下最新 JSON 报告：

- `docs/reports/controlled_pilot_delivery_gate/`
- `docs/reports/controlled_pilot_launch_gate/`
- `docs/reports/controlled_pilot_launch_package/`
- `docs/reports/controlled_pilot_status_summary/`
- `docs/reports/controlled_pilot_operator_packet/`
- `docs/reports/controlled_pilot_console_verify/`
- `docs/reports/production_landing_refresh_status/`
- `docs/reports/production_landing_status/`
- `docs/reports/business_system_read_smoke/`

当这些证据共同证明 demo 业务只读接口已通过、没有业务写入、控制台验证通过、且唯一剩余缺口为 `business_system:real_business_system_required` 时，运行包才会输出 `status=ready` 与 `controlled_internal_pilot=Go`。

## 执行命令

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\controlled_pilot_run_packet.py
```

默认输出：

- `docs/reports/controlled_pilot_run_packet/*.json`
- `docs/reports/controlled_pilot_run_packet/*.md`

## 操作员命令

运行包会输出以下安全命令：

- `verify_console`：执行一键本地受控试点验证。
- `refresh_status`：按当前本地 env 刷新落地状态链路。
- `refresh_run_packet`：重新生成运行包。
- `rollback_console`：停止本地受控试点控制台。

这些命令不要求在命令行填写 token 或连接串。

## 状态口径

- `status=ready` 且 `controlled_internal_pilot=Go`：当前证据支持进入受控内网试点窗口。
- `status=partial`：证据缺失或不完整，需要补齐后再进入试点窗口。
- `status=blocked`：发现 secret-like 文本、公网生产边界变化或关键安全边界异常，必须先处理。
- `public_production_direct_launch=No-Go`：不允许直接公网生产上线。

## 当前真实生产缺口

在没有真实业务系统的前提下，运行包允许把 `business_system:real_business_system_required` 作为受控内网试点的已接受剩余缺口。该缺口不能用于真实生产验收。拿到真实业务系统后，必须重新执行真实只读 smoke、真实 readiness gate、人工复核和 Go/No-Go。

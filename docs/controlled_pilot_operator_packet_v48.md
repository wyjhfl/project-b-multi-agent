# 受控试点操作员交接包

## 目标

`scripts/controlled_pilot_operator_packet.py` 用于生成受控企业内网试点的操作员交接包。交接包把当前试点总状态、窗口记录、窗口健康状态、运营台 smoke、操作员命令、角色职责、证据路径和回滚边界集中到一份只读报告中，便于试点启动、交接和人工复核。

## 默认边界

- 只读取结构化报告，不连接真实外部系统。
- 不调用真实 LLM。
- 不连接 PostgreSQL、Redis 或外部 MCP。
- 不写业务数据、审计数据或指标数据。
- 不读取或输出 token、API Key、数据库连接串、Redis 连接串等 secret 原文。
- `public_production_direct_launch` 始终保持 `No-Go`。

## 输入证据

默认读取以下目录中的最新 JSON 报告：

- `docs/reports/controlled_pilot_status_summary/`
- `docs/reports/controlled_pilot_launch_package/`
- `docs/reports/controlled_pilot_window_record/`
- `docs/reports/controlled_pilot_window_status/`
- `docs/reports/operations_console_landing_smoke/`

如果任一关键证据缺失、解析失败、状态阻断、发现疑似 secret，交接包不会给出受控试点 `Go`。

## 执行命令

推荐使用 PowerShell 入口刷新总状态摘要并生成操作员交接包：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\controlled_pilot_operator_packet.ps1
```

也可以直接运行 Python 脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\controlled_pilot_operator_packet.py
```

默认输出：

- `docs/reports/controlled_pilot_operator_packet/*.json`
- `docs/reports/controlled_pilot_operator_packet/*.md`

## 本地受控试点控制台

如需在当前机器启动本地受控试点运营台，使用以下命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\controlled_pilot_console_up.ps1
```

如需执行一次完整本地受控试点验证，推荐使用一键入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\controlled_pilot_console_verify.ps1
```

该入口会在同一个 PowerShell 会话中完成启动、运营台 smoke、刷新操作员交接包和停止清理，适合交接前复核。

执行一键验证时会先运行本地预检；预检发现端口占用、前端构建产物缺失、运行时缺失或残留 PID 文件时，不会继续启动服务，并会生成失败验证报告。

一键验证还会生成独立结论报告：

- `docs/reports/controlled_pilot_console_verify/*.json`
- `docs/reports/controlled_pilot_console_verify/*.md`

默认绑定：

- 后端：`http://127.0.0.1:8000`
- 前端运营台：`http://127.0.0.1:3003/operations`

启动脚本只绑定 `127.0.0.1`，不会读取或写入 `.env`，不会要求输入 token、API key 或连接串，并会刷新操作员交接包。进程记录写入：

该入口使用前端生产启动方式；如果前端构建产物缺失，先在 `frontend/` 下执行 `npm.cmd run build`。

- `docs/reports/controlled_pilot_console/controlled_pilot_console_processes.json`

停止本地受控试点运营台：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\controlled_pilot_console_down.ps1
```

该停止脚本只读取上述进程记录并停止对应本地进程；缺少进程记录时返回 `skipped`，不做额外清理。

## 状态口径

- `status=ready` 且 `controlled_internal_pilot=Go`：当前证据支持进入受控企业内网试点窗口。
- `status=partial`：仍需人工复核或补齐证据，不应扩大范围。
- `status=blocked`：发现 secret-like 内容、关键证据不可用或安全边界异常，必须先处理阻断项。
- `public_production_direct_launch=No-Go`：不代表公网生产可直接上线，任何公网或扩大范围发布都必须重新人工 Go/No-Go。

## 操作员关注项

- `window.window_id`：当前受控试点窗口 ID。
- `evidence_paths`：本次交接包引用的证据路径。
- `operator_commands`：建议操作员复核或刷新证据的命令。
- `pilot_roles`：试点角色职责。
- `rollback_required=true`：试点必须保留回滚能力。
- `external_expansion_requires_new_manual_go_no_go=true`：扩大范围必须重新人工评审。

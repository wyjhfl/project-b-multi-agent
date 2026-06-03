# v3.7 Phase 17.2 External MCP acceptance gate

## 目标

Phase 17.2 建立真实外部 MCP 验收门禁，覆盖 real mode opt-in、command allowlist、tool allowlist、超时、生命周期、审批和审计边界。

本阶段只读，不启动真实 MCP 进程，不执行 `tools/list` 或 `tools/call`，不连接真实外部 MCP Server。

## 入口

```powershell
python scripts/external_mcp_acceptance_gate.py
```

可指定输出目录：

```powershell
python scripts/external_mcp_acceptance_gate.py --output-dir docs/reports/external_mcp_acceptance_gate/
```

默认输出：

- JSON：`docs/reports/external_mcp_acceptance_gate/*_external_mcp_acceptance_gate.json`
- Markdown：`docs/reports/external_mcp_acceptance_gate/*_external_mcp_acceptance_gate.md`

## 门禁项

- `real_mode_opt_in`：`MCP_MODE=real` 才允许进入真实 MCP 验收。
- `command_configured`：必须配置 `MCP_SERVER_COMMAND`。
- `command_allowlist`：必须配置 `MCP_SERVER_COMMAND_ALLOWLIST`，且 command 在 allowlist 内。
- `tool_allowlist`：必须配置 `MCP_TOOL_ALLOWLIST`，避免真实外部工具无限暴露。
- `timeout_config`：必须保留超时配置，避免外部 MCP 卡死。
- `lifecycle_hardening`：复核 stdio client 生命周期、stderr 边界和失败路径测试。
- `approval_audit_boundary`：真实工具调用仍必须经过 ToolGateway、PolicyEngine、审批和审计链路。
- `fake_fixture_coverage`：默认测试继续使用 fake stdio fixture，不连接真实外部 MCP。

## 状态语义

- `skipped`：缺少真实 MCP opt-in 或必需配置。
- `partial`：配置条件齐备，但本阶段未启动真实 MCP 进程，只能进入人工 opt-in 演练准备。
- `blocked`：发现 command 未在 allowlist、工具 allowlist 缺失或只读边界被破坏。
- `success`：保留给后续真实 MCP opt-in 演练完成并形成脱敏证据后使用。

## 只读边界

- 不启动 MCP subprocess。
- 不执行真实 `tools/list`。
- 不执行真实 `tools/call`。
- 不连接真实外部 MCP Server。
- 不绕过 ToolGateway、PolicyEngine、审批链路或审计链路。
- 不读取或输出真实 secret 原文。
- 默认 fake/offline，默认 pytest/CI 不连接真实外部 MCP。
- 不宣称真实外部 MCP 生产验收完成。

## 验证

```powershell
python -m pytest tests/test_external_mcp_acceptance_gate_v372.py -q
python -m pytest tests/test_mcp_stdio_client_v31.py tests/test_mcp_gateway_v03.py -q
docker compose config
```

## 后续衔接

- Phase 17.3：Real LLM provider acceptance gate。
- 后续真实 MCP opt-in 演练必须单独提供 command、allowlist、脱敏日志、审批和审计证据。

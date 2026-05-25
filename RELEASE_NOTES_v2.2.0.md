# Project B v2.2.0 - MCP Stdio Runtime Hardening

## 1. Highlights

- Introduced real MCP stdio protocol path behind configuration, while keeping default behavior unchanged.
- Completed Phase 3.1-3.5 scope for MCP stdio implementation and hardening.
- Preserved legacy runtime and graph runtime default-off semantics.

## 2. MCP stdio capabilities

- `StdioMCPClient` supports subprocess stdio transport (`shell=False`).
- JSON-RPC handshake and requests supported:
  - `initialize`
  - `tools/list`
  - `tools/call`
- `ToolGateway` can discover and call MCP tools in `MCP_MODE=real` with configured fake stdio fixture.
- Mapping from MCP tool metadata to `ToolSpec` is supported with defaults (`risk_level=medium`, `permission_scope=read`).

## 3. Lifecycle hardening

- Added lifecycle health snapshot fields (started/initialized/process/pid/error/counters).
- Added request serialization lock to prevent request id and stream races.
- Added conservative restart recovery after timeout/crash/protocol stream failures.
- Added bounded stderr capture for diagnostics.
- `call_tool` failure path does not auto-replay to avoid duplicate high-risk operations.

## 4. Security boundaries

- `shell=False` enforced for subprocess launch.
- Command allowlist supported in real mode.
- MCP command/args come from server config, not from user prompt/query.
- `env_allowlist` supported; complete sandbox isolation is still a later phase.
- High-risk MCP tools must still go through ToolGateway/Policy/HITL path; no bypass.

## 5. Verification

- Focus tests:
  - `python -m pytest tests/test_mcp_stdio_client_v31.py tests/test_mcp_gateway_v03.py tests/test_v03_closure_mcp_docker.py -q`
  - `python -m pytest tests/test_runtime_hardening_v055.py -q`
- Full regression:
  - `python -m pytest -q`
- Result baseline: **582 passed**.
- Docker checks:
  - `docker compose config` passed
  - `docker compose build app` passed

## 6. Known limitations

- Real external MCP Server production acceptance is not completed.
- Complete sandbox/runtime isolation is not completed.
- Real LLM / LLM-as-Judge integration is not completed.
- Frontend approval UI is not implemented.
- Full LangGraph native Command resume is still roadmap.

## 7. Upgrade notes

- Default behavior remains unchanged (`MCP_MODE=fake`).
- To enable real stdio path, configure:
  - `MCP_MODE=real`
  - `MCP_SERVER_COMMAND`
  - `MCP_SERVER_ARGS`
  - `MCP_SERVER_COMMAND_ALLOWLIST`
  - optional `MCP_SERVER_WORKDIR` / `MCP_SERVER_ENV_ALLOWLIST`
- PostgreSQL mode unchanged:
  - `STORAGE_BACKEND=postgres`
  - valid `DATABASE_URL`

## 8. Next phase

- Continue Phase 3.5+ security hardening and real external MCP server acceptance.
- Do not create release tag automatically in this prep step.

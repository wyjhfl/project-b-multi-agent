# Release Review - v2.2 MCP Stdio Runtime Hardening

## Scope

- Release prep target: `v2.2.0` (no tag in this step).
- Focus: Phase 3.1-3.5 MCP stdio protocol path, lifecycle hardening, and release/documentation alignment.

## Changed modules

- MCP client/runtime:
  - `app/tools/mcp/stdio_client.py`
  - `tests/fixtures/fake_mcp_stdio_server.py`
- Gateway integration and real-mode registration:
  - `app/main.py`
  - `app/harness/gateway/tool_gateway.py` (existing integration path validated)
- Release prep alignment:
  - `pyproject.toml`
  - `README.md`
  - `AGENTS.md`
  - `docs/mcp_stdio_plan_v3.md`
  - `docs/enterprise_pilot_plan_v2.md`
  - `tests/test_runtime_hardening_v055.py`
  - `RELEASE_NOTES_v2.2.0.md`

## Tests

- MCP-focused:
  - `python -m pytest tests/test_mcp_stdio_client_v31.py tests/test_mcp_gateway_v03.py tests/test_v03_closure_mcp_docker.py -q`
- Runtime hardening:
  - `python -m pytest tests/test_runtime_hardening_v055.py -q`
- Full suite:
  - `python -m pytest -q`
- Result baseline: **582 passed**.

## Docker verification

- `docker compose config` passed.
- `docker compose build app` passed.

## Boundaries

- Default remains `MCP_MODE=fake`; real mode requires explicit command/allowlist config.
- Validation is based on fake stdio MCP server fixture.
- Real external MCP Server production acceptance is not completed.
- Complete sandbox isolation is not completed.
- No real LLM / LLM-as-Judge integration.
- No frontend work in this phase.
- No change to legacy resume semantics or graph runtime default-off behavior.

## Go / No-Go

- **Go for release prep commit**: yes.
- **Tag creation**: pending explicit human confirmation (do not auto-tag in this step).

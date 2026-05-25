# Project B v2.1.0 - Graph Runtime Adapter

## Highlights

- Added GraphCheckpointStore with SQLite and PostgreSQL implementations.
- Added GraphRuntimeAdapter behind the default-off `graph_runtime_enabled=false` feature flag.
- Added graph interrupt -> approval mapping for high-risk graph keyword tool execution.
- Added GraphResumeAdapter for `graph_keyword` single-tool approval resume.
- Added resume idempotency and restart recovery coverage.
- Hardened graph resume failure paths so failed or exceptional tool calls consume the checkpoint and do not execute twice.

## Verification

- `python -m pytest -q`: `553 passed`
- `docker compose config`: passed
- `docker compose build app`: passed

## Boundaries

- This is not full LangGraph native Command resume.
- Real MCP stdio is not implemented.
- Real LLM / LLM-as-Judge is not implemented.
- Frontend approval UI is not implemented.
- `graph_runtime_enabled` remains default `false`.
- Legacy resume semantics are unchanged.

## Upgrade notes

- Default behavior is unchanged after upgrading to `v2.1.0`.
- Enable graph runtime explicitly with `GRAPH_RUNTIME_ENABLED=true`.
- PostgreSQL mode still requires `STORAGE_BACKEND=postgres` and a non-empty `DATABASE_URL`.
- SQLite remains the default storage backend.

## Recommended next phase

- Phase 3: real MCP stdio client planning and implementation.

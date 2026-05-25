# Release Review: v2.1 Graph Runtime Adapter

## Release summary

- Final release version: `v2.1.0`
- Release name: Project B v2.1.0 - Graph Runtime Adapter
- Baseline commit before release prep: `7df8923 chore: finalize graph runtime phase 2 cleanup`
- Release-prep commit: created after this review, version bump, release notes, tests, and Docker verification are committed; see final report / git history
- Tag status: pending until human confirmation; do not create tag automatically

## Version files updated

- `pyproject.toml`: `version = "2.1.0"`
- `app/main.py`: FastAPI app version and `/health` version set to `2.1.0`
- `README.md`: release badge and version route updated to `v2.1.0`
- `AGENTS.md`: version route updated to `v2.1.0`
- Tests with version assertions updated to `2.1.0`

## Phase 2.1-2.5 completed items

- Phase 2.1 GraphCheckpointStore: added `graph_run_states` schema, SQLite / PostgreSQL checkpoint stores, Store Factory getter, and idempotent `claim_for_resume`.
- Phase 2.2 GraphRuntimeAdapter: added default-off `graph_runtime_enabled` feature flag; supports keyword low-risk smoke path and writes staged checkpoints.
- Phase 2.3 graph interrupt -> approval mapping: high-risk graph keyword path creates interrupt payload, approval, and pending checkpoint.
- Phase 2.4 GraphResumeAdapter: routes `approval.payload.mode == "graph_keyword"` with `checkpoint_id` to graph resume; atomically claims checkpoint, executes the approved single tool, updates task / approval payload / checkpoint, and cancels checkpoint on reject.
- Phase 2.5 release cleanup: added graph resume failure-path tests, aligned docs wording, updated test count, and generated release documentation.

## Current capability

- Default `graph_runtime_enabled=false`; legacy keyword / multitool / approval resume behavior is unchanged.
- With `graph_runtime_enabled=true`, graph_keyword single-tool approval resume has a minimal closed loop.
- Supports checkpoint create, pending interrupt, claim, mark_resumed, mark_cancelled, and expire_old.
- Supports restart recovery through persisted approval payload, checkpoint store, task store, and gateway.
- Resume idempotency is protected by checkpoint claim plus approval payload `resumed=true`.
- Failure path is hardened: if the tool returns failure or raises, the checkpoint is still consumed, task is marked failed, and repeated resume does not call the tool again.

## Explicit non-goals

- No full LangGraph native checkpoint / Command interrupt / Command resume.
- No real MCP stdio.
- No real LLM / LLM-as-Judge.
- No frontend approval UI.
- Do not present deterministic multi-role orchestration as autonomous multi-agent.
- Do not enable graph runtime, auth, rbac, postgres, or redis by default.
- Do not change legacy resume semantics.

## Verification results

- `python -m pytest tests/test_graph_resume_v24.py tests/test_graph_interrupt_approval_v23.py tests/test_graph_runtime_adapter_v22.py -q`: `20 passed`
- `python -m pytest tests/test_hitl_v04.py tests/test_approval_resume_v042.py tests/test_v043_full_resume.py tests/test_langgraph_kernel_v11.py -q`: `45 passed`
- `python -m pytest -q`: `553 passed`
- `docker compose config`: passed
- `docker compose build app`: passed, app image built as `project-b-multi-agent-app:latest`

## Known boundaries

- Graph resume only covers `graph_keyword` single-tool approval resume.
- High-risk graph path remains adapter-level interrupt / approval mapping, not LangGraph native Command interrupt.
- GraphResumeAdapter does not execute later graph nodes and does not handle multi-round interrupts.
- PostgreSQL / Redis still require explicit enterprise pilot configuration; default storage backend remains SQLite.
- InMemoryUserStore is not a production user store.
- Approval UI remains API / minimal UI capability, not a complete frontend approval console.

## Release recommendation

- If release-prep verification passes, recommend creating `v2.1.0` tag only after human confirmation.
- Recommended next phase after release: Phase 3 real MCP stdio client planning.

# Release Review: v2.1 Graph Runtime Adapter

## Baseline

- Baseline commit: `46776e2 feat: add graph approval resume adapter`
- Scope: Phase 2.5 release cleanup + failure-path hardening
- Formal version: keep `v2.0.1`; this cleanup does not change `pyproject.toml` / `app.version` and does not create a tag
- Tag recommendation: wait for human confirmation of release notes and version strategy before tagging

## Phase 2.1-2.5 completed items

- Phase 2.1 GraphCheckpointStore: added `graph_run_states` schema, SQLite / PostgreSQL checkpoint stores, Store Factory getter, and idempotent `claim_for_resume`.
- Phase 2.2 GraphRuntimeAdapter: added default-off `graph_runtime_enabled` feature flag; supports keyword low-risk smoke path and writes staged checkpoints.
- Phase 2.3 graph interrupt -> approval mapping: high-risk graph keyword path creates interrupt payload, approval, and pending checkpoint.
- Phase 2.4 GraphResumeAdapter: routes `approval.payload.mode == "graph_keyword"` with `checkpoint_id` to graph resume; atomically claims checkpoint, executes the approved single tool, updates task / approval payload / checkpoint, and cancels checkpoint on reject.
- Phase 2.5 release cleanup: added graph resume failure-path tests, aligned docs wording, updated test count, and generated this release review.

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

- `python -m pytest tests/test_graph_resume_v24.py tests/test_graph_interrupt_approval_v23.py tests/test_graph_checkpoint_store_v21.py -q`: `31 passed`
- `python -m pytest tests/test_graph_runtime_adapter_v22.py tests/test_hitl_v04.py tests/test_approval_resume_v042.py tests/test_v043_full_resume.py tests/test_langgraph_kernel_v11.py -q`: `51 passed`
- `python -m pytest -q`: `553 passed`
- `docker compose config`: passed
- `docker compose build app`: passed, app image built

## Known boundaries

- Graph resume only covers `graph_keyword` single-tool approval resume.
- High-risk graph path remains adapter-level interrupt / approval mapping, not LangGraph native Command interrupt.
- GraphResumeAdapter does not execute later graph nodes and does not handle multi-round interrupts.
- PostgreSQL / Redis still require explicit enterprise pilot configuration; default storage backend remains SQLite.
- InMemoryUserStore is not a production user store.
- Approval UI remains API / minimal UI capability, not a complete frontend approval console.

## Release recommendation

- Keep this as Phase 2 graph runtime adapter cleanup for now; do not tag immediately.
- Publishing `v2.1` or another formal version should wait for human confirmation of release notes, version strategy, and deployment window.

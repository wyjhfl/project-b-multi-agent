# Changelog

Notable changes to this project. Earlier incremental history is recorded in git tags (`v1.0.0` – `v3.5.0`) and the commit log.

## [5.0.0] - 2026-07-26

Agent capability upgrade and hardening release. All defaults remain offline (fake provider / mock generator); new capabilities are demoable offline and gated by settings switches.

### Added

- LLM function calling: provider layer accepts OpenAI-format `tools`/`tool_choice` and parses `tool_calls`; new opt-in `LLMToolPlanner` (`PLANNER_MODE=llm`) selects tools via function calling with JSON Schema argument validation and a deterministic keyword-planner fallback chain; optional Coordinator LLM routing (`COORDINATOR_LLM_ENABLED`).
- Streaming: `generate_stream` in the provider layer (LiteLLM `stream=True`, fake provider chunk simulation) and an SSE endpoint `POST /nl2sql/stream` (stage → sql_delta → guard → execution → done) reusing the full guardrail/audit chain, with a streaming mode in the operator console.
- `OpenAICompatibleProvider`: first-class direct OpenAI-compatible HTTP path (httpx only, no litellm install required), with typed error mapping and retry policy.
- High-risk HITL demo tool `simulate_refund_order` (in-memory simulation) so the approval → checkpoint → resume flow is live-demoable end to end.
- Real-model pilot tooling: `scripts/run_llm_pilot.py` (preflight → NL2SQL eval sample → redacted report); refuses to generate reports without explicit real-LLM configuration; `--dry-run` is clearly watermarked.
- Token/cost pre-estimation feeding budget checks (replaces constant zero estimates).
- Alembic migration `003` fixing `runtime_tool_metrics.status` schema drift.
- MIT license, changelog, README architecture diagram and badges.

### Changed

- The keyword main path now executes through a compiled LangGraph `StateGraph` (`graph.invoke`) with a conditional approval edge and a sequential fallback; docstrings updated to describe the self-built checkpoint state machine honestly.
- Coordinator and KeywordPlanner now share a single routing table (previously two divergent copies).
- `GET /tasks/{id}` returns proper `404` for unknown tasks (previously `200` with an error body); frontend updated accordingly.
- MCP stdio client aligned with protocol revision 2024-11-05: `protocolVersion`/`capabilities`/`clientInfo` handshake with version negotiation, `notifications/initialized`, and `tools/call` `isError` mapping.
- 19 previously unauthenticated API endpoints now enforce `require_permission` when auth is enabled.
- SQLite NL2SQL executor opens true read-only connections (`file:...?mode=ro`).
- Documentation (README, architecture, interview guide, resume pack, demo script) rewritten to match verified behavior, with explicit default/opt-in tags per capability.

### Fixed

- Reviewer no longer approves failed `auto`-mode results (previously reported "执行成功" on failures with a partial answer).
- Dead code removed from `sql_guard`; budget checks no longer receive hard-coded `estimated_cost=0.0`.

### Tests

- Offline suite: 863 passed / 4 skipped / 0 failed (previous baseline 722; +141 new tests covering function calling, streaming, graph execution, auth coverage, migration chain, MCP protocol, HITL demo, and pilot tooling).

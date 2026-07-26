# Architecture Overview

Project B is organized around a governed Agent Runtime. The main goal is to make agent execution explainable, controllable, auditable, and demoable in an offline environment.

## Runtime Layers

```text
User Request
  -> FastAPI API layer
  -> Agent Runtime / Harness
  -> Multi-Agent Orchestrator
  -> ToolGateway / PolicyEngine / Approval
  -> Storage / Audit / Metrics / Trace
  -> Operator Console / Observability UI
```

The keyword main path inside the Agent Runtime executes through a compiled LangGraph StateGraph (`assemble_context -> plan -> execute -> verify -> respond`, with a conditional edge that skips `verify` when the task enters `waiting_approval`). If LangGraph is unavailable, the kernel falls back to an equivalent sequential run; the trace `task_started` event records `engine=langgraph|sequential`. The nl2sql, multitool, and multi_agent modes are pipeline-style execution. Checkpoint persistence and HITL resume are handled by the custom GraphRuntimeAdapter state machine (default off), not by the native LangGraph checkpointer.

## Planner Layer

- KeywordPlanner (default): deterministic keyword-to-tool routing rules, shared as a single rule source with the Coordinator.
- LLMToolPlanner (opt-in via `PLANNER_MODE=llm`): converts ToolGateway specs into OpenAI function-calling tools, asks the provider to pick one, validates the returned arguments against the tool input schema (undeclared arguments are dropped), and falls back to the KeywordPlanner on any failure (no tools, provider error, no tool call, unknown tool, invalid arguments).
- Governance is planner-independent: policy evaluation and high-risk approval happen in the kernel execute stage, so an LLM-selected high-risk tool still stops at `waiting_approval`.

## LLM Provider Layer

- Providers: fake (default, offline), LiteLLM (optional dependency), and a direct OpenAI-compatible HTTP path (httpx only).
- Capabilities: function calling (tools/tool_choice), streaming generation, typed error mapping with retries, and heuristic token/cost estimation that feeds budget checks. Defaults keep cost estimates at zero and behavior offline.

## Multi-Agent Roles

- Coordinator: classifies intent and selects the execution mode (rule-based; optional LLM routing decision behind `COORDINATOR_LLM_ENABLED`, default off, cross-checked against the keyword rules).
- Analyst: builds a simple execution plan.
- Executor: calls tools, NL2SQL, or fallback runtime paths.
- Reviewer: reviews the result and records the final state; failed or blocked results are rejected instead of being approved, and blocked results do not get a fallback suggestion.

The current system is rule-based role orchestration. It should not be described as fully autonomous multi-agent software.

## Governance Flow

All meaningful execution paths are designed to pass through explicit boundaries:

1. API request enters FastAPI.
2. Runtime creates task context and trace events.
3. Multi-Agent orchestrator selects role flow.
4. ToolGateway handles tool calls.
5. PolicyEngine and OperationWhitelist check risky operations.
6. Approval flow can pause and resume execution.
7. Audit and metrics stores keep evidence.
8. Observability UI shows trace and trajectory.

## NL2SQL Streaming Path

`POST /nl2sql/stream` (behind `NL2SQL_STREAM_ENABLED`, default on) is a server-sent-events endpoint in the API layer. It reuses the same guarded pipeline as `/nl2sql/execute` — input guardrails, prompt-injection guard, SQL generation, SELECT-only SQLGuard, read-only execution, and audit — and emits `stage`, incremental `sql_delta`, `guard`, `execution`, and a final `done` event carrying the full execute response. SQL deltas are chunked after the pipeline completes (chunk size `llm_stream_chunk_chars`), which keeps the guard/audit chain fully intact; true per-token provider passthrough is a possible later step. The frontend consumes the stream with plain `fetch` + `ReadableStream`, no extra dependency.

## Observability

The Observability page exposes two views:

- Trace timeline: raw event sequence for a task.
- Multi-Agent Trajectory: role-oriented execution visualization with role, action, status, selected mode, executed mode, fallback, and approval signals.

## Storage Boundary

SQLite is the default local demo backend. PostgreSQL and Redis are optional pilot paths and should only be enabled with explicit configuration.

## External Service Boundary

The default test and demo path does not call real LLM APIs, real MCP servers, real business systems, or real identity providers. Real integrations are opt-in only.

- The stdio MCP client is aligned with MCP 2024-11-05 (initialize handshake with version negotiation, `notifications/initialized`, `tools/call` isError mapping), but the default remains the in-process fake MCP client.
- Real-model pilots go through `scripts/run_llm_pilot.py`, which refuses to produce reports unless the real-LLM opt-in settings are explicitly configured; `--dry-run` exercises the same flow offline with the fake provider.

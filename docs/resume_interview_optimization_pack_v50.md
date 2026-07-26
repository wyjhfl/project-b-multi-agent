# Resume and Interview Pack

## Project Name

Enterprise Multi-Agent Runtime and Operator Console Prototype

## One-line Summary

Built a FastAPI + Next.js Multi-Agent Runtime prototype: LangGraph-executed keyword main path, rule-based role orchestration, governed tool execution, HITL approval/resume, SSE streaming NL2SQL, opt-in LLM function-calling planner, audit trail, and trajectory visualization. It runs offline by default.

## Resume Bullets

- Built a governed Agent Runtime whose keyword main path executes through a compiled LangGraph StateGraph (`graph.invoke` with a conditional approval edge, equivalent sequential fallback), combined with a custom checkpoint state machine (GraphRuntimeAdapter) for HITL approval/resume — not the native LangGraph checkpointer.
- Implemented an LLM provider layer with function calling (tools/tool_choice), streaming generation, a direct OpenAI-compatible HTTP path (httpx only, no litellm required), typed error mapping with retries, and heuristic token/cost estimation feeding budget checks; fake/offline provider is the default.
- Implemented an opt-in LLM function-calling tool planner (`PLANNER_MODE=llm`) with JSON-schema argument validation (undeclared arguments dropped to prevent injection) and a deterministic keyword-planner fallback for every failure point; policy and approval governance is enforced regardless of planner.
- Added an SSE streaming NL2SQL endpoint (`/nl2sql/stream`) that reuses the guarded pipeline end to end: prompt-injection guard, SELECT-only SQLGuard, read-only SQLite execution, and audit.
- Delivered a live HITL demo path: a high-risk simulated-write tool triggers `waiting_approval`, then approve/auto-resume or reject/cancel, with full audit and trace evidence.
- Designed rule-based Multi-Agent role orchestration (Coordinator, Analyst, Executor, Reviewer) with a single routing-rule source, explainable confidence scoring, an optional LLM routing decision (default off), and a reviewer that rejects failed/blocked results instead of reporting false success.
- Aligned the stdio MCP client with MCP 2024-11-05: initialize handshake with version negotiation, `notifications/initialized`, and `tools/call` isError mapping; fake MCP remains the default.
- Added pytest coverage (860+ offline tests) for graph execution, LLM planner fallback, streaming, multi-agent review, MCP protocol, approval, audit, security, storage, and deployment guard paths.
- Ran a controlled real-model pilot (agnes-2.0-flash via an OpenAI-compatible gateway, 2026-07-26): 17 NL2SQL eval cases, 94.1% pass, 12/14 LLM cases real generations (latency p50 3.3s / p95 8.7s, ~9.8k tokens); first run exposed two authentic integration bugs — markdown-fenced JSON breaking parsing (fixed with tolerant three-stage extraction + regression tests) and gateway per-minute rate limits collapsing the batch to mock fallback (mitigated with request pacing and retry backoff). Redacted reports in `docs/reports/real_llm_pilot/`.

## Defaults and Opt-in Switches

Say clearly in interviews which capabilities are on by default and which require opt-in:

- On by default (offline-capable): fake LLM provider, fake MCP, LangGraph keyword main path (auto-fallback to sequential), SSE streaming NL2SQL (`NL2SQL_STREAM_ENABLED=true`), high-risk demo tool (`DEMO_HIGH_RISK_TOOL_ENABLED=true`, pure in-memory simulation).
- Opt-in (default off): LLM function-calling planner (`PLANNER_MODE=llm`; still demoable offline with the fake provider), Coordinator LLM routing (`COORDINATOR_LLM_ENABLED=true`), GraphRuntimeAdapter checkpoint path (`GRAPH_RUNTIME_ENABLED=true`), real LLM pilot (`REAL_LLM_ACCEPTANCE_ENABLED=true` plus provider/model/key; `scripts/run_llm_pilot.py` refuses to generate reports without them), real MCP (`MCP_MODE=real` plus command/allowlists), auth/RBAC, PostgreSQL/Redis.
- Do not claim: autonomous multi-agent collaboration, production-ready delivery, completed real-LLM/MCP production acceptance.

## 2-minute Pitch

This project is not a simple chatbot. It is an enterprise-style Agent Runtime prototype. I focused on three engineering problems: agent execution must be explainable, tool execution must be governed, and the demo must be stable without depending on real external providers.

In the demo, I create a multi-agent task and open the Observability page. The Multi-Agent Trajectory view shows how the system routes the task, plans execution, executes the selected mode, reviews the result, and records fallback or approval signals. This demonstrates LLM application engineering beyond basic API calls.

## Interview Q&A

### Is it fully autonomous multi-agent software?

No. It is rule-based role orchestration. That is intentional because the project emphasizes enterprise control, observability, and safety boundaries.

### Why is real LLM disabled by default?

To keep CI and demos stable. Real LLM usage is opt-in and requires explicit provider, key, budget, and smoke-test configuration.

### What is the strongest engineering point?

The closed governance loop: tool gateway, policy checks, approval/resume, audit trail, metrics, fallback, eval, and trajectory visualization. The governance layer is planner-independent — even when the LLM planner selects a high-risk tool, execution still stops at approval.

### How is LangGraph actually used?

The keyword main path is compiled into a LangGraph StateGraph and executed via `graph.invoke`, with a conditional edge for the approval interrupt. Checkpoint/resume is a custom state machine, not the native LangGraph checkpointer, because approval persistence, idempotent resume, and audit are coupled to the existing stores. Say this precisely; do not claim full native Command resume.

### What is missing before real production?

Real IdP integration, real business-system read-only acceptance, PostgreSQL/Redis production smoke, real MCP allowlist acceptance, secret rotation, and backup/restore drills.

## Demo Commands

```powershell
python scripts/init_demo_db.py
python scripts/start_dev.py
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Docker:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_up.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_smoke.ps1
```

# Project B - Multi-Agent Runtime Showcase

Project B is an enterprise-style Multi-Agent Runtime prototype for resume and interview demonstration. It focuses on explainable orchestration, governed tool execution, human approval, auditability, and trajectory visualization.

## Positioning

- Core domain: Multi-Agent orchestration, tool governance, HITL approval, audit trail, observability, and trajectory visualization.
- Default mode: fake/offline. Local demo does not require a real LLM, external MCP server, business system, PostgreSQL, or Redis.
- Target roles: AI Agent engineer, LLM application engineer, AI platform backend engineer.
- Boundary: production-grade engineering prototype, not public-production-ready software.
- `public_production_direct_launch=No-Go`.

## Core Capabilities

1. Multi-agent role orchestration: Coordinator, Analyst, Executor, and Reviewer (rule-based; optional LLM routing decision via `COORDINATOR_LLM_ENABLED`, default off).
2. Graph execution: the keyword main path runs through a compiled LangGraph StateGraph (`graph.invoke`) with a conditional approval edge, and falls back to equivalent sequential execution if LangGraph is unavailable. Checkpoint/HITL resume uses a custom GraphRuntimeAdapter state machine, not the native LangGraph checkpointer.
3. Tool governance: ToolGateway, PolicyEngine, OperationWhitelist, approval, and audit.
4. HITL live demo: a high-risk simulated-write tool `simulate_refund_order` (in-memory simulation only, `DEMO_HIGH_RISK_TOOL_ENABLED`, default on) triggers `waiting_approval`, then approve/auto-resume or reject/cancel, fully audited.
5. LLM engineering boundary: fake/offline by default; optional real providers via LiteLLM or a direct OpenAI-compatible HTTP path; function calling, streaming, budget with heuristic token/cost estimation, cache, fallback, and guardrails.
6. LLM tool planning (opt-in): `PLANNER_MODE=llm` enables function-calling tool selection with argument validation and deterministic keyword-planner fallback; default remains the keyword planner. Demoable offline with the fake provider.
7. NL2SQL: guarded SELECT-only pipeline plus an SSE streaming endpoint `/nl2sql/stream` (`NL2SQL_STREAM_ENABLED`, default on, offline-capable) that reuses the same injection guard, SQLGuard, read-only executor, and audit chain.
8. MCP: fake MCP by default; the stdio MCP client implements the MCP 2024-11-05 initialize handshake, `notifications/initialized`, and `tools/call` isError mapping.
9. Observability: task trace and Multi-Agent Trajectory visualization.
10. Operator console: Tasks, Approvals, Trace, Audit, Metrics, Tools, NL2SQL, RBAC, and LLM status pages.
11. Real-model pilot tooling: `scripts/run_llm_pilot.py` + `docs/llm_pilot_runbook.md` (opt-in only; refuses to generate reports without explicit real-LLM configuration; `--dry-run` demonstrates the full flow offline).

## Tech Stack

- Backend: Python 3.11, FastAPI, Pydantic, SQLAlchemy, Alembic.
- Agent runtime: custom Harness, rule-based Multi-Agent orchestrator, LangGraph StateGraph for the keyword main path (sequential fallback), optional GraphRuntimeAdapter checkpoint path.
- LLM providers: fake (default), LiteLLM (optional dependency), direct OpenAI-compatible HTTP (httpx only).
- Tool protocol: fake MCP by default, MCP 2024-11-05-aligned stdio client, ToolGateway.
- Frontend: Next.js, React, TypeScript.
- Storage: SQLite demo by default; PostgreSQL and Redis are optional pilot paths.
- Tests: pytest; default tests do not call real external services.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python scripts/init_demo_db.py
python scripts/start_dev.py
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Docker demo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_up.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_down.ps1
```

## Demo Flow

1. Open Dashboard and explain the project as an enterprise Multi-Agent Runtime.
2. Create a `multi_agent` task on the Tasks page.
3. Open Observability, enter the `task_id`, and show Trace plus Multi-Agent Trajectory.
4. Open Approvals to explain human approval for high-risk tools.
5. Open Audit and Metrics to explain governance and observability.
6. Open Tools and NL2SQL to explain unified tool execution boundaries.

## Project Structure

```text
app/                 backend core
app/agent/           multi-agent roles and orchestration
app/harness/         runtime, LLM, MCP, approval, audit, eval modules
app/api/             FastAPI routes
app/storage/         SQLite/PostgreSQL store abstraction
frontend/            Next.js operator console
scripts/             startup, demo, health check, read-only checks
tests/               core regression tests
docs/                architecture, deployment, demo, interview materials
```

## Verification

```powershell
python -m pytest
python -m py_compile app/api/observability.py app/api/operations.py scripts/start_dev.py
```

Targeted tests for the newer capabilities (all offline, fake provider):

```powershell
python -m pytest tests/test_kernel_graph_invoke.py tests/test_llm_planner.py
python -m pytest tests/test_llm_provider_tools_stream.py tests/test_nl2sql_stream.py
python -m pytest tests/test_mcp_stdio_client_v31.py
python -m pytest tests/test_high_risk_approval_demo_v445.py tests/test_multi_agent_reviewer_routing_v445.py
python -m pytest tests/test_run_llm_pilot.py
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
```

## Interview Materials

- `docs/architecture.md`: architecture overview.
- `docs/interview_guide.md`: interview Q&A.
- `docs/resume_interview_optimization_pack_v50.md`: resume bullets and 2-minute pitch.
- `docs/interview_demo_readiness_v50.md`: read-only pre-interview check.
- `docs/demo_script_v1.md`: demo script.
- `docs/llm_pilot_runbook.md`: opt-in real-model pilot runbook.

## Recommended GitHub Description

Enterprise-style Multi-Agent Runtime prototype: LangGraph-executed keyword main path, rule-based role orchestration, governed tool execution, HITL approval/resume with a live high-risk demo tool, SSE streaming NL2SQL, opt-in LLM function-calling planner, MCP 2024-11-05-aligned stdio client, audit trail, operator console, and trajectory visualization. It runs offline by default and does not require a real LLM or external MCP server.

Avoid overclaiming: do not describe it as fully autonomous multi-agent software, public-production-ready software, or completed real-provider production acceptance.

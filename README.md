# Project B - Multi-Agent Runtime Showcase

Project B is an enterprise-style Multi-Agent Runtime prototype for resume and interview demonstration. It focuses on explainable orchestration, governed tool execution, human approval, auditability, and trajectory visualization.

## Positioning

- Core domain: Multi-Agent orchestration, tool governance, HITL approval, audit trail, observability, and trajectory visualization.
- Default mode: fake/offline. Local demo does not require a real LLM, external MCP server, business system, PostgreSQL, or Redis.
- Target roles: AI Agent engineer, LLM application engineer, AI platform backend engineer.
- Boundary: production-grade engineering prototype, not public-production-ready software.
- `public_production_direct_launch=No-Go`.

## Core Capabilities

1. Multi-agent role orchestration: Coordinator, Analyst, Executor, and Reviewer.
2. Tool governance: ToolGateway, PolicyEngine, OperationWhitelist, approval, and audit.
3. LLM engineering boundary: fake/offline by default, optional real provider opt-in, budget, cache, fallback, and guardrails.
4. Observability: task trace and Multi-Agent Trajectory visualization.
5. Operator console: Tasks, Approvals, Trace, Audit, Metrics, Tools, NL2SQL, RBAC, and LLM status pages.

## Tech Stack

- Backend: Python 3.11, FastAPI, Pydantic, SQLAlchemy, Alembic.
- Agent runtime: custom Harness, rule-based Multi-Agent orchestrator, optional LangGraph adapter.
- Tool protocol: fake MCP, stdio MCP client skeleton, ToolGateway.
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

## Recommended GitHub Description

Enterprise-style Multi-Agent Runtime prototype with rule-based role orchestration, governed tool execution, HITL approval/resume, audit trail, LLM fallback, NL2SQL demo, operator console, and trajectory visualization. It runs offline by default and does not require a real LLM or external MCP server.

Avoid overclaiming: do not describe it as fully autonomous multi-agent software, public-production-ready software, or completed real-provider production acceptance.

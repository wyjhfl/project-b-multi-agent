# Resume and Interview Pack

## Project Name

Enterprise Multi-Agent Runtime and Operator Console Prototype

## One-line Summary

Built a FastAPI + Next.js Multi-Agent Runtime prototype with rule-based role orchestration, governed tool execution, HITL approval/resume, audit trail, LLM fallback, NL2SQL demo, and trajectory visualization. It runs offline by default.

## Resume Bullets

- Designed a rule-based Multi-Agent execution flow with Coordinator, Analyst, Executor, and Reviewer roles, and recorded task trajectory for explainability.
- Implemented ToolGateway, PolicyEngine, OperationWhitelist, and HITL approval to govern tool calls and high-risk operations.
- Built LLM provider abstraction with fake/offline default path, optional real-provider opt-in, budget, cache, fallback, and guardrails.
- Built an operator console covering Tasks, Approvals, Trace, Audit, Metrics, Tools, NL2SQL, and Multi-Agent Trajectory visualization.
- Added pytest coverage for multi-agent execution, MCP gateway, approval, audit, security, LLM fallback, storage, and deployment guard paths.

## 2-minute Pitch

This project is not a simple chatbot. It is an enterprise-style Agent Runtime prototype. I focused on three engineering problems: agent execution must be explainable, tool execution must be governed, and the demo must be stable without depending on real external providers.

In the demo, I create a multi-agent task and open the Observability page. The Multi-Agent Trajectory view shows how the system routes the task, plans execution, executes the selected mode, reviews the result, and records fallback or approval signals. This demonstrates LLM application engineering beyond basic API calls.

## Interview Q&A

### Is it fully autonomous multi-agent software?

No. It is rule-based role orchestration. That is intentional because the project emphasizes enterprise control, observability, and safety boundaries.

### Why is real LLM disabled by default?

To keep CI and demos stable. Real LLM usage is opt-in and requires explicit provider, key, budget, and smoke-test configuration.

### What is the strongest engineering point?

The closed governance loop: tool gateway, policy checks, approval/resume, audit trail, metrics, fallback, eval, and trajectory visualization.

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

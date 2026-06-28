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

## Multi-Agent Roles

- Coordinator: classifies intent and selects the execution mode.
- Analyst: builds a simple execution plan.
- Executor: calls tools, NL2SQL, or fallback runtime paths.
- Reviewer: reviews the result and records the final state.

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

## Observability

The Observability page exposes two views:

- Trace timeline: raw event sequence for a task.
- Multi-Agent Trajectory: role-oriented execution visualization with role, action, status, selected mode, executed mode, fallback, and approval signals.

## Storage Boundary

SQLite is the default local demo backend. PostgreSQL and Redis are optional pilot paths and should only be enabled with explicit configuration.

## External Service Boundary

The default test and demo path does not call real LLM APIs, real MCP servers, real business systems, or real identity providers. Real integrations are opt-in only.

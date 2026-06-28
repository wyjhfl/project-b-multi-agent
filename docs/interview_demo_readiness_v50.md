# Interview Demo Readiness

This read-only checklist verifies whether the project is ready for an interview demo. It does not call real LLM APIs, connect to real business systems, or print secrets.

## Required Materials

- `README.md`
- `docs/architecture.md`
- `docs/interview_guide.md`
- `docs/resume_interview_optimization_pack_v50.md`
- `docs/demo_script_v1.md`

## Local Check

```powershell
python -m py_compile app/api/observability.py app/api/operations.py scripts/start_dev.py
python scripts/interview_demo_readiness.py
```

Focused tests, when pytest is installed:

```powershell
python -m pytest tests/test_multi_agent_v03.py tests/test_multi_agent_trajectory_v11.py tests/test_trajectory_eval_v11.py tests/test_operations_summary_v312.py -q
```

## Demo Path

1. Start backend and frontend.
2. Create a `multi_agent` task.
3. Open Observability and enter the `task_id`.
4. Show Multi-Agent Trajectory: role chain, selected mode, executed mode, fallback, approval, and step action.
5. Open Audit, Metrics, and Approvals to explain governance.

## Boundaries

- `public_production_direct_launch=No-Go`
- `real_business_system_connected=false`
- `business_data_written=false`
- `secret_plaintext_output=false`
- Multi-Agent is rule-based role orchestration, not fully autonomous multi-agent software.

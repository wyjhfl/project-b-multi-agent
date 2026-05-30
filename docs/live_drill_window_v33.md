# v3.3 Optional Live Drill Window Runbook

## 1. Scope

- This runbook defines a controlled **optional live drill window** for Project B v3.3.
- The drill is for internal pilot handoff evidence only.
- It is **not** public production launch approval.
- It is **not** real LLM production acceptance completion.
- It is **not** production-grade SSO/OIDC completion.

## 2. Default Boundaries

- Default mode remains `fake/offline`.
- Default pytest/CI does not call real LLM.
- No real secret plaintext is committed or exported.
- No user data deletion.
- No automatic report cleanup.
- No `.env` mutation by this drill workflow.

## 3. Live Drill Preconditions

### 3.1 Service window checks

- `/health`
- `/deployment/check`
- `/operations/summary`

### 3.2 Automation/report generation readiness

- `scripts/acceptance_snapshot.py`
- `scripts/demo_artifact_bundle.py`
- `scripts/failure_diagnostics.py`
- `scripts/config_drift_check.py`
- `scripts/governance_policy_summary.py`

### 3.3 Real LLM opt-in checks

Required env names:

- `REAL_LLM_SMOKE_ENABLED`
- `REAL_LLM_ACCEPTANCE_ENABLED`
- `REAL_LLM_PREFLIGHT_ENABLED`
- `REAL_LLM_PREFLIGHT_NETWORK_CHECK`
- `REAL_LLM_MODEL`
- `REAL_LLM_API_KEY_ENV`
- env pointed by `REAL_LLM_API_KEY_ENV` must exist

If any required condition is missing, the drill result must be `skipped` with explicit missing list.

### 3.4 OIDC live drill checks

- `OIDC_ENABLED=true` (optional live drill mode only)
- `OIDC_ISSUER_URL`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET_ENV`
- env pointed by `OIDC_CLIENT_SECRET_ENV` must exist
- `OIDC_REDIRECT_URI` should be HTTPS in production drills

## 4. Status Vocabulary

Allowed status words:

- `success`: all required checks passed
- `skipped`: any required real LLM/OIDC condition missing (must list missing items)
- `blocked`: required script/interface missing or hard blocker
- `partial`: required real LLM/OIDC conditions are complete, but service window is unavailable
- `failed`: check execution attempted but failed unexpectedly

## 5. Suggested Execution

Run read-only precheck and evidence generation summary:

```bash
python scripts/live_drill_window.py
python scripts/live_drill_window.py --output-dir .tmp_live_drill
```

Outputs:

- JSON summary
- Markdown summary
- default output dir: `docs/reports/live_drill_window/`

## 6. Evidence and Handoff

Each run should archive:

- status (`success/skipped/blocked/partial/failed`)
- missing conditions (if skipped)
- service availability snapshot
- script readiness snapshot
- real LLM opt-in readiness snapshot
- OIDC live drill readiness snapshot
- boundary declarations

## 7. Non-goals

- No direct real external LLM execution in default flow
- No business logic change
- No release/tag operation in this phase

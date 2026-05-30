# v3.3 Phase 13.3: Governance Policy Summary (Read Only)

## 1. Positioning

- This document is the governance entry for Project B operations/pilot handoff.
- It summarizes already-established boundaries across security, release, opt-in real LLM, OIDC, report archiving, config drift, and retention policy.
- This is a read-only governance summary and does not change runtime behavior.

## 2. Core Governance Boundaries

### 2.1 Default Runtime and Test Path

- Default runtime path is fake/offline.
- Default pytest/CI path does not call real external LLM.

### 2.2 Real LLM Opt-In Control

- Real LLM is opt-in only.
- Required environment variables must be complete before execution.
- If required variables are missing, execution must be recorded as `skipped`.
- Missing-variable cases must not be reported as success.

### 2.3 Secret and Credential Boundary

- Do not commit real secrets or credentials:
  - API key
  - token
  - client_secret
  - JWT_SECRET
  - DATABASE_URL
  - REDIS_URL
- Reports and exported artifacts must keep redaction boundaries.

### 2.4 Audit Export and Redaction

- Audit export must keep whitelist/redaction boundary.
- No raw prompt or plaintext secret in audit export path.

### 2.5 OIDC Boundary

- OIDC scope is minimal IdP drill and config validation boundary.
- This does not equal production-grade SSO/OIDC completion.

### 2.6 Report Index and Retention Boundary

- Report index/retention is read-only.
- Stale candidates are listed only.
- No automatic deletion, no user data deletion.

### 2.7 Config Drift Boundary

- Config drift checklist is read-only.
- No automatic fix.
- No automatic `.env` mutation.

### 2.8 Release and Tag Boundary

- Historical tags are immutable and must not be moved.
- Release creation is manual.
- After manual release creation, documentation closure is required.

### 2.9 Non-Claim Boundary

- Do not claim public production direct launch.
- Do not claim real LLM production acceptance completion.
- Do not claim production-grade SSO/OIDC completion.
- Do not claim multitenancy completion.
- Do not claim complex BI full completion.

## 3. Governance Evidence Entry

- Main plan:
  - `docs/v3_3_operational_automation_governance_plan.md`
- Report index/retention:
  - `scripts/report_index.py`
  - `docs/report_index_retention_runbook_v33.md`
- Config drift:
  - `scripts/config_drift_check.py`
  - `docs/config_drift_checklist_v33.md`
- Real LLM opt-in logs:
  - `docs/real_llm_optional_retry_log_v32.md`
  - `docs/real_llm_pilot_execution_log_v31.md`
- OIDC drill:
  - `docs/oidc_minimal_idp_drill_v31.md`
- Post-release handoff records:
  - `docs/post_release_check_v3.2.0.md`
  - `docs/post_release_check_v3.1.0.md`

## 4. Optional Read-Only Script

- Script: `scripts/governance_policy_summary.py`
- Output: JSON + Markdown
- Default output directory:
  - `docs/reports/governance_policy/`
- Supports:
  - `--output-dir`

Example:

```bash
python scripts/governance_policy_summary.py
python scripts/governance_policy_summary.py --output-dir .tmp_governance_policy_check
```

## 5. Verification Baseline

```bash
python -m pytest tests/test_governance_policy_summary_v333.py -q
python -m pytest tests/test_report_index_v331.py tests/test_config_drift_v332.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
```

## 6. Phase Boundary Reminder

- No version change in this phase.
- No tag creation/push in this phase.
- No GitHub Release creation in this phase.
- No real external LLM execution in this phase.

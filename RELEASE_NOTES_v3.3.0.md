# RELEASE NOTES v3.3.0

## Summary

v3.3.0 = **Operational Automation & Governance**.

This release-prep round consolidates operations automation and governance entry points for internal pilot handoff.

## Phase Coverage

### Phase 13.1 ? Report index & retention

- Added read-only report index tooling for acceptance snapshots, demo artifacts, and failure diagnostics.
- Retention outputs list stale candidates only; no automatic deletion.

### Phase 13.2 ? Config drift checklist

- Added read-only config drift checklist and report generation.
- Focused on `.env.example`, `.env.production.example`, deployment guard, runtime and prod compose key alignment.

### Phase 13.3 ? Governance policy summary

- Added governance policy summary document and read-only summary script.
- Consolidated boundaries for audit redaction, OIDC drill, real LLM opt-in, release/tag handling, and report retention.

### Phase 13.4 ? Operations automation script polish

- Unified script summary metadata and CLI conventions across acceptance/demo/diagnostics/index/drift/governance flows.
- Preserved read-only boundaries; no destructive commands.

### Phase 13.5 ? Optional live drill window

- Added optional live drill runbook and read-only precheck script.
- Added status vocabulary (`success/skipped/blocked/partial/failed`) and required-condition tracking.
- Fixed status logic: when required real LLM/OIDC conditions are missing, result is **skipped** (not partial).

## Boundaries (still enforced)

- Default fake/offline mode.
- Default pytest/CI does not call real external LLM.
- Phase 13.5 in this round did not execute real external LLM.
- Live drill remains read-only precheck; missing opt-in conditions must be skipped.
- No plaintext secrets committed (API key/token/client_secret/JWT_SECRET/DATABASE_URL/REDIS_URL).
- Not a claim of public production direct launch.
- Not a claim of real LLM production acceptance completion.
- Not a claim of production-grade SSO/OIDC, multitenancy, or complex BI full completion.

## Release-prep note

- This round prepares v3.3.0 materials only.
- No v3.3.0 tag created in this round.
- No GitHub Release created in this round.

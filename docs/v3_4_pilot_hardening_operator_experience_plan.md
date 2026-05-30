# v3.4 Pilot Hardening & Operator Experience Plan

## Positioning

- v3.4 = **Pilot Hardening & Operator Experience**.
- Focus: intranet pilot hardening, operator experience, failure-recovery rehearsal quality, and optional integration readiness.
- Not a claim of public production direct launch.
- Not a claim of real LLM production acceptance completion.
- Not a claim of production-grade SSO/OIDC, multitenancy, or complex BI full completion.

## Baseline and boundaries

- Current app version remains `3.3.0` in this planning phase.
- `v3.3.0` GitHub Release is completed; historical tags remain unchanged.
- Planning-only round: no business logic change, no version bump, no tag, no Release creation.
- Default fake/offline remains unchanged.
- Default pytest/CI no real external LLM remains unchanged.
- No plaintext secrets in docs/scripts/tests.

## Priority

- P0: Phase 14.1 + 14.2
- P1: Phase 14.3 + 14.4
- P2: Phase 14.5 + 14.6

## Phase 14.1 - Operator workflow polish (P0)

- Goal
  - Polish daily operator entry points, runbook cross-links, status interpretation, and read-only evidence navigation.
- Scope
  - `/operations` and operations-facing docs/runbook linkage; read-only UI copy and navigation cues only.
- Out of scope
  - No write/delete action, no real LLM execution path, no auth model redesign.
- Validation
  - `python -m pytest tests/test_runtime_hardening_v055.py -q`
  - `docker compose config`
  - frontend lint/build where touched.
- Done criteria
  - Operator can find key runbooks and evidence paths quickly; empty/skipped/error states remain explicit and read-only.

## Phase 14.2 - Incident rehearsal pack (P0)

- Goal
  - Build a standard incident rehearsal pack for core failure scenarios.
- Scope
  - Service unavailable, config drift, report missing, OIDC/real LLM skipped, compose/prod-compose failure scenarios.
- Out of scope
  - No destructive remediation automation, no data deletion.
- Validation
  - Focused pytest for rehearsal tooling/docs checks + `docker compose config`.
- Done criteria
  - Rehearsal checklist and evidence format are complete, reproducible, and clear about skipped vs failed.

## Phase 14.3 - Evidence archive manifest (P1)

- Goal
  - Provide one unified manifest for acceptance/demo/failure/governance/live-drill/report-index artifacts.
- Scope
  - Read-only manifest/index generation and runbook references.
- Out of scope
  - No auto retention deletion.
- Validation
  - Targeted manifest tests + regression checks for existing report scripts.
- Done criteria
  - Artifact families are discoverable from one index with timestamp/path/status metadata.

## Phase 14.4 - Optional integration readiness matrix (P1)

- Goal
  - Summarize readiness of optional integrations.
- Scope
  - Real LLM opt-in, OIDC, external MCP, Postgres/Redis, and frontend build network dependency posture.
- Out of scope
  - No real external integration execution by default.
- Validation
  - Read-only matrix generation checks + existing runtime hardening baseline.
- Done criteria
  - Matrix clearly shows ready/missing/skipped conditions with no secret value exposure.

## Phase 14.5 - Pilot handoff checklist polish (P2)

- Goal
  - Refine intranet pilot handoff package for operators and reviewers.
- Scope
  - Roles/permissions, recovery steps, acceptance evidence, known limitations.
- Out of scope
  - No production rollout claim, no architecture rewrite.
- Validation
  - Checklist consistency scan + focused pytest baseline.
- Done criteria
  - Handoff checklist is complete, actionable, and boundary-consistent.

## Phase 14.6 - v3.4 release prep (P2)

- Goal
  - Prepare version sync, release notes/review, verification matrix, and tag-decision precheck for v3.4.
- Scope
  - Release prep artifacts only.
- Out of scope
  - This planning round does not execute v3.4 release prep.
- Validation
  - To be defined in Phase 14.6 execution turn.
- Done criteria
  - Release-prep checklist is ready for execution in a dedicated round.

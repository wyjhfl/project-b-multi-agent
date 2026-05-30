# v3.3 Phase 13.4: Operations Automation Scripts Polish (Read Only)

## 1. Scope

- This document normalizes CLI usage and output semantics for operations automation scripts.
- Changes in this phase are polish-only and do not change business logic.
- Boundaries remain read-only by default.

## 2. Script Matrix

- `scripts/acceptance_snapshot.py`
  - CLI: `--output-dir`, `--base-url`
  - Default output: `docs/reports/acceptance_snapshots/`
  - Summary fields: `status`, `generated_at`, `commit`, `mode`, `read_only`, `real_llm_executed`, `json_path`, `markdown_path`, `output_dir`
- `scripts/demo_artifact_bundle.py`
  - CLI: `--artifact-dir`, `--base-url`, `--seed-input`, `--online-input`, `--artifact-run-dir`, `--pilot-report-dir`
  - Default output: `docs/reports/demo_artifacts/`
  - Summary fields: `status`, `generated_at`, `commit`, `mode`, `read_only`, `real_llm_executed`, `artifact_run_dir`, `summary_path`, `output_dir`
- `scripts/failure_diagnostics.py`
  - CLI: `--output-dir`, `--base-url`, `--skip-compose-checks`
  - Default output: `docs/reports/failure_diagnostics/`
  - Summary fields: `status`, `generated_at`, `commit`, `mode`, `read_only`, `real_llm_executed`, `json_path`, `markdown_path`, `output_dir`
- `scripts/report_index.py`
  - CLI: `--output-dir`, `--keep-latest`, `--retain-days`
  - Default output: `docs/reports/report_index/`
  - Summary fields: `status`, `generated_at`, `commit`, `mode`, `read_only`, `real_llm_executed`, `json_path`, `markdown_path`, `output_dir`
- `scripts/config_drift_check.py`
  - CLI: `--output-dir`
  - Default output: `docs/reports/config_drift/`
  - Summary fields: `status`, `generated_at`, `commit`, `mode`, `read_only`, `real_llm_executed`, `json_path`, `markdown_path`, `output_dir`
- `scripts/governance_policy_summary.py`
  - CLI: `--output-dir`
  - Default output: `docs/reports/governance_policy/`
  - Summary fields: `status`, `generated_at`, `commit`, `mode`, `read_only`, `real_llm_executed`, `json_path`, `markdown_path`, `output_dir`
- `scripts/demo_e2e.ps1`
  - CLI: `-BaseUrl`, `-SkipSeed`, `-ArtifactDir`
  - Default output: `docs/reports/demo_artifacts/` (timestamp subdir per run)
  - Produces: `seed_summary.json`, `online_smoke_result.json`, `demo_e2e_summary.json`, plus acceptance snapshot and pilot report index

## 3. Status Vocabulary

- Common status values used across script summary:
  - `ok`
  - `failed`
  - `skipped`
  - `partial`
  - `completed`
  - `completed_with_skipped_online_checks`
  - `completed_with_partial_online_checks`

## 4. Read-Only Boundary

- No user data deletion.
- No auto cleanup of report files.
- No `.env` modification.
- No reading/output of real secret plaintext.
- No real external LLM execution by default.

## 5. Runbook Links

- Acceptance snapshot: `docs/acceptance_snapshot_runbook_v32.md`
- Demo artifact bundle: `docs/demo_artifact_bundle_runbook_v32.md`
- Failure diagnostics pack: `docs/failure_diagnostics_pack_v32.md`
- Report index retention: `docs/report_index_retention_runbook_v33.md`
- Config drift checklist: `docs/config_drift_checklist_v33.md`
- Governance policy summary: `docs/governance_policy_summary_v33.md`

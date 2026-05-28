# v3.2 Phase 12.3: Demo Artifact Bundle Runbook

## 1. Goal

- Unify `demo_e2e` artifact output and produce an archivable demo evidence bundle.
- Keep default fake/offline behavior and do not call real external LLM.
- If service is unavailable, online smoke is marked skipped and not reported as success.

## 2. Commands

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo_e2e.ps1
```

Optional:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo_e2e.ps1 -ArtifactDir docs/reports/demo_artifacts
powershell -ExecutionPolicy Bypass -File scripts/demo_e2e.ps1 -BaseUrl http://localhost:8000
powershell -ExecutionPolicy Bypass -File scripts/demo_e2e.ps1 -SkipSeed
```

## 3. Output

- default root: `docs/reports/demo_artifacts/`
- per-run folder: `<timestamp>_<short_commit>/`

Bundle files:

- `demo_e2e_summary.json`
- `online_smoke_result.json`
- `seed_summary.json`
- `pilot_report_index.json`
- `operations_summary.json` (when online check succeeds)
- `acceptance_snapshot/*.json`
- `acceptance_snapshot/*.md`

## 4. Summary fields

- `generated_at`
- `commit`
- `mode=fake_offline_default`
- `real_llm_executed=false`
- `seed.status/path`
- `online_smoke.status/path/skipped_reason`
- `operations_summary.status/path/reason`
- `acceptance_snapshot.json_path/markdown_path`
- `pilot_report_index.path/report_dir/total_reports`
- `boundary_declarations`

## 5. Sanitization boundary

- no prompt/query/raw_prompt/sql_prompt/messages/input raw text
- no API key/token/client_secret/password/JWT_SECRET/DATABASE_URL/REDIS_URL plaintext
- no DSN password plaintext

## 6. Common outcomes

- Service unavailable:
  - `online_smoke.status=skipped`
  - `demo_e2e_summary.status=completed_with_skipped_online_checks`
- Service partially available:
  - `online_smoke.status=partial`
  - `demo_e2e_summary.status=completed_with_partial_online_checks`

## 7. Verification

```bash
python -m pytest tests/test_demo_artifact_bundle_v323.py -q
python -m pytest tests/test_demo_seed_data_v311.py tests/test_acceptance_snapshot_v321.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
docker compose config
```

## 8. Boundary declaration

- not public production approval
- not real LLM production acceptance
- no raw prompt / no secrets

# v3.4 Phase 14.2 故障演练包

## 目标

Phase 14.2 建立只读故障演练包，把常见企业内网试点故障转为可重复演练、可归档证据、可解释 `skipped` / `blocked` / `partial` 的流程。

## 只读边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 默认不启动服务。
- 不修改环境变量或 `.env`。
- 不删除用户数据。
- 不自动清理报告。
- 不读取或输出真实 secret 原文。
- 不执行真实外网 LLM。

## 覆盖场景

- `service_unavailable`
- `docker_compose_config_failure`
- `prod_compose_missing_required_env`
- `deployment_check_ok_false`
- `operations_unavailable_or_empty`
- `acceptance_snapshot_online_skipped`
- `demo_e2e_online_smoke_skipped`
- `failure_diagnostics_blocked_findings`
- `report_index_empty_or_stale_candidates`
- `config_drift_warnings`
- `governance_or_live_drill_skipped`
- `oidc_secret_env_missing`
- `real_llm_opt_in_missing_or_skipped`

## 状态词

- `success`：演练条件或证据存在，未发现该场景阻断。
- `skipped`：缺少可选条件、服务不可达或本轮未请求该只读检查。
- `blocked`：缺少必需前置条件，需要人工处理后再演练。
- `partial`：部分在线检查可用，部分不可用。
- `failed`：只读检查执行失败。

## 使用方式

默认不运行 compose 检查：

```powershell
python scripts/incident_rehearsal_pack.py --output-dir docs/reports/incident_rehearsal
```

需要把 `docker compose config` 纳入只读检查时显式开启：

```powershell
python scripts/incident_rehearsal_pack.py --output-dir docs/reports/incident_rehearsal --run-compose-checks
```

## 输出字段

- `generated_at`
- `commit`
- `version`
- `mode`
- `read_only`
- `real_llm_executed`
- `scenarios`
- `recommended_runbooks`
- `missing_conditions`
- `status`
- `status_vocabulary`
- `boundary_declarations`
- `output_dir`

## 验证

```powershell
python -m pytest tests/test_incident_rehearsal_pack_v342.py -q
python scripts/incident_rehearsal_pack.py --output-dir .tmp_incident_rehearsal_check
python -m pytest tests/test_failure_diagnostics_v324.py tests/test_live_drill_window_v335.py -q
docker compose config
```

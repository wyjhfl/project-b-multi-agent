# v3.4 Phase 14.4 可选集成准备度矩阵

## 目标

Phase 14.4 建立可选真实集成准备度矩阵，只做只读预检，不执行真实集成。该矩阵用于判断真实 LLM、OIDC、外部 MCP、Postgres/Redis、前端构建网络依赖等是否具备演练条件。

## 只读边界

- 只检查配置存在性和本地可验证条件。
- 不读取真实 secret 值，仅输出 env name 与 `present=true/false`。
- 不调用真实外网 LLM。
- 不连接真实外部 MCP。
- 不要求默认配置启用 auth、RBAC、Redis 或 PostgreSQL。
- 默认 fake/offline。

## 覆盖矩阵

- real LLM opt-in readiness
- OIDC readiness
- external MCP readiness
- Postgres readiness
- Redis readiness
- frontend build/network dependency readiness
- deployment guard readiness
- audit export/redaction readiness

## 使用方式

```powershell
python scripts/optional_integration_readiness.py --output-dir docs/reports/optional_integration_readiness
```

## 输出字段

- `generated_at`
- `commit`
- `version`
- `integrations`
- `readiness_status`
- `missing_conditions`
- `skipped_reasons`
- `risk_notes`
- `recommended_next_actions`
- `boundary_declarations`
- `read_only`
- `real_llm_executed`

## 状态解释

- `ready`：全部本地条件和配置存在性检查满足。
- `partial`：部分集成满足，部分缺少条件。
- `skipped`：缺少可选真实集成演练条件。

缺少真实 LLM/OIDC/外部 MCP opt-in 条件时必须 `skipped`，不得伪造成成功。

## 验证

```powershell
python -m pytest tests/test_optional_integration_readiness_v344.py -q
python scripts/optional_integration_readiness.py --output-dir .tmp_optional_integration_check
python -m pytest tests/test_config_drift_v332.py tests/test_live_drill_window_v335.py -q
docker compose config
```

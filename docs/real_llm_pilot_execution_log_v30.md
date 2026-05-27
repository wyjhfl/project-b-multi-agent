# v3.0 Phase 10.1：真实 LLM 受控试点执行记录

## 1. 执行目标

- 为 v3.0 Phase 10.1 建立可复现的真实 LLM opt-in 执行记录。
- 在满足显式环境前提时执行 smoke，并归档脱敏报告。
- 在环境不满足时明确 `skipped`，不伪造成功报告。

## 2. 执行前提（opt-in 环境变量）

必需：

- `REAL_LLM_SMOKE_ENABLED=true`
- `REAL_LLM_ACCEPTANCE_ENABLED=true`
- `REAL_LLM_PREFLIGHT_ENABLED=true`
- `REAL_LLM_PREFLIGHT_NETWORK_CHECK=true`
- `REAL_LLM_MODEL`
- `REAL_LLM_API_KEY_ENV`

可选：

- `REAL_LLM_BASE_URL`
- `REAL_LLM_PILOT_REPORT_DIR`

边界：

- 不写入 API key 原文，不在文档中记录 token/client_secret。
- 不记录 prompt 原文。

## 3. 执行命令与报告目录

执行命令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/real_llm_smoke.ps1
```

报告目录（默认）：

- `docs/reports/real_llm_pilot/`

## 4. 结果记录模板

- executed / skipped
- provider / model / base_url_summary
- report json/md path
- request_id
- latency / tokens / cost
- fallback_reason
- budget_action
- cache_hit
- error_type
- operator notes

## 5. 本轮执行记录（2026-05-27）

- status：`skipped`
- executed：`false`
- 原因：当前 shell 未配置真实 LLM opt-in 环境变量，按边界要求不执行真实外网 LLM。
- 缺失变量：
  - `REAL_LLM_SMOKE_ENABLED`
  - `REAL_LLM_ACCEPTANCE_ENABLED`
  - `REAL_LLM_PREFLIGHT_ENABLED`
  - `REAL_LLM_PREFLIGHT_NETWORK_CHECK`
  - `REAL_LLM_MODEL`
  - `REAL_LLM_API_KEY_ENV`
- 可选变量（未配置）：
  - `REAL_LLM_BASE_URL`
  - `REAL_LLM_PILOT_REPORT_DIR`
- 报告归档：本轮未生成真实外网报告（无 JSON/Markdown 新报告）。
- operator notes：等待用户在安全环境下手动注入 opt-in 变量后重试。

## 6. 说明

- 本文档仅记录执行事实与脱敏元信息，不包含密钥原文。
- 本轮未执行真实外网 LLM，不影响默认 fake/offline 与默认 pytest/CI 行为。

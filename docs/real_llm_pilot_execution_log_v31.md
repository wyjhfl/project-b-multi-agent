# v3.1 Phase 11.3：真实 LLM opt-in 实测执行记录

## 1. 执行目标

- 仅在用户显式提供 opt-in 环境变量时执行真实外网 LLM smoke。
- 归档脱敏 pilot report 与执行结果（success / fallback / error / skipped）。
- 环境不满足时必须记录 `skipped`，不伪造成功报告。

## 2. opt-in 前提变量

必需：

- `REAL_LLM_SMOKE_ENABLED=true`
- `REAL_LLM_ACCEPTANCE_ENABLED=true`
- `REAL_LLM_PREFLIGHT_ENABLED=true`
- `REAL_LLM_PREFLIGHT_NETWORK_CHECK=true`
- `REAL_LLM_MODEL`
- `REAL_LLM_API_KEY_ENV`
- `REAL_LLM_API_KEY_ENV` 指向的真实 key 环境变量（仅检查存在性，不记录值）

可选：

- `REAL_LLM_BASE_URL`
- `REAL_LLM_PILOT_REPORT_DIR`

## 3. 执行命令（满足前提时）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/real_llm_smoke.ps1
```

默认报告目录：

- `docs/reports/real_llm_pilot/`

## 4. 本轮执行记录（2026-05-27）

- status: `skipped`
- executed: `false`
- 是否执行真实外网 LLM：`否`
- 原因：当前 shell 未配置 Phase 11.3 必需 opt-in 变量，按边界要求跳过执行。

缺失必需变量：

- `REAL_LLM_SMOKE_ENABLED`
- `REAL_LLM_ACCEPTANCE_ENABLED`
- `REAL_LLM_PREFLIGHT_ENABLED`
- `REAL_LLM_PREFLIGHT_NETWORK_CHECK`
- `REAL_LLM_MODEL`
- `REAL_LLM_API_KEY_ENV`
- `REAL_LLM_API_KEY_ENV` 指向 key 环境变量：未检测（因 env 名本身缺失）

可选变量状态：

- `REAL_LLM_BASE_URL`: 未配置
- `REAL_LLM_PILOT_REPORT_DIR`: 未配置

报告归档结果：

- 本轮未生成新的真实外网 pilot report JSON/Markdown。
- 未生成 request_id / tokens / cost / fallback / budget / cache 的真实执行条目。

operator notes：

- 等待用户在安全环境中注入 opt-in 变量后重试。
- 重试时仍保持脱敏边界：不记录 prompt 原文，不记录 API key/token/password/client_secret/DSN 密码原文。

## 5. 状态值约定

- `success`
- `network_error`
- `auth_error`
- `rate_limit`
- `budget_block`
- `fallback`
- `skipped`


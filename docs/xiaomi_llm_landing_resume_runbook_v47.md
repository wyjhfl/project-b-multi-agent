# v4.7 小米 LLM 落地恢复推进 Runbook

本文用于在不落盘密钥的前提下恢复小米真实 LLM 预检证据，并顺序刷新生产落地状态、人工签署证据状态、阻塞解除报告和最终验证报告。

## 使用场景

- `production_landing_status` 仍为 `partial`。
- `blocked_domains` 包含 `real_llm`。
- 当前只需要补齐小米 LLM 真实网络预检证据，不修改 `.env` 或模板文件。
- 人工签署仍需要业务负责人按模板确认后写入正式记录；脚本不会自动批准或自动签署。

## 推荐命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1
```

脚本会执行：

1. 使用 `Read-Host -AsSecureString` 读取 `XIAOMI_LLM_API_KEY`。
2. 仅注入当前 PowerShell 进程环境。
3. 执行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\production_landing_env_runner.py --action xiaomi-llm-preflight`。
4. 执行 `python scripts/manual_signoff_evidence_ack_status.py`。
5. 执行 `python scripts/manual_signoff_record_validator.py`。
6. 执行 `python scripts/production_landing_blocker_resolution.py`。
7. 执行 `python scripts/production_landing_refresh_status.py --closure-evidence docs/reports/launch_blocker_closure/closure_evidence.draft.json`。
8. 执行 `python scripts/production_landing_final_verification.py`。
9. 在 `finally` 中恢复或清除当前进程的 `XIAOMI_LLM_API_KEY`。

## 已有进程环境变量时

如果外部 secret 管理已经把 `XIAOMI_LLM_API_KEY` 注入当前进程：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1 -UseExistingEnv
```

## 安全边界

- 不写 `.env`、`.env.example`、`.env.production.example`。
- 不把 API key 写入命令行参数、报告、Markdown、日志或测试夹具。
- 报告只允许输出 `api_key_present`、`network_check_executed`、`real_llm_executed` 等布尔状态。
- `public_production_direct_launch` 必须保持 `No-Go`。
- 真实预检成功不代表公网生产直上，也不会自动完成人工签署。

## 完成判定

- `production_landing_xiaomi_llm_preflight` 最新报告为 `status=success`。
- 最新预检报告中 `network_check_executed=true` 且 `real_llm_executed=true`。
- `manual_signoff_evidence_ack_status` 推荐接受项补齐到 `4/4`。
- `production_landing_blocker_resolution` 中 `real_llm_preflight` 变为 `resolved`。
- `production_landing_final_verification` 不再因 `real_llm_preflight:not_success` 缺口失败。
- 人工签署应写入 `docs/reports/manual_signoff_package/manual_signoff_record.json`；未形成正式记录时脚本只读取 `manual_signoff_record.draft.json` 作为待审草稿，模板仅用于生成样板。
- 人工签署记录必须保持 `public_production_direct_launch=No-Go`。

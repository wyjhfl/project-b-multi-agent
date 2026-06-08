# v4.8 生产落地签核收口 Runbook

本文用于在所有技术证据已完成后，执行最后的人工签核收口。该流程只进入受控试点 Go，不代表公网生产直上。

## 适用前提

- 通用 OpenAI-compatible 真实 LLM preflight 最新报告为 `success`；历史 Xiaomi 兼容路径仅作为 fallback 证据。
- PostgreSQL、Redis、external MCP staging smoke 已形成可审查证据。
- 业务系统只读 smoke 已形成可审查证据。
- `manual_signoff_evidence_ack_status` 推荐接受项为 `4/4`。
- 当前剩余 blocker 为 `manual_signoff:not_completed` 或 `action_pack:required_inputs_remaining`。

## 交互式执行

推荐在 Windows PowerShell 中运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\production_landing_signoff_closeout.ps1
```

脚本会提示输入：

- `release_manager name or staff id`
- `security_reviewer name or staff id`
- `business_owner name or staff id`
- `operations_owner name or staff id`

随后需要两次输入 `YES`：

- 确认已人工复核所有推荐证据。
- 确认进入受控试点 Go，同时 `public_production_direct_launch` 仍保持 `No-Go`。

## 非交互式执行

如需由受控自动化系统注入签核人姓名或工号，可运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts/production_landing_signoff_closeout.py --release-manager <name-or-id> --security-reviewer <name-or-id> --business-owner <name-or-id> --operations-owner <name-or-id> --confirm-manual-signoff --confirm-controlled-pilot-go
```

`<name-or-id>` 必须是人员姓名或工号，不得是 API key、token、连接串、密码或其他 secret。

## 脚本执行链路

`production_landing_signoff_closeout.py` 会按顺序执行：

1. 填充 `manual_signoff_record.draft.json`。
2. 提升为正式 `manual_signoff_record.json`。
3. 刷新 blocker resolution。
4. 刷新 landing status。
5. 执行 final verification。

任一步失败时，closeout 报告保持 `partial` 或 `blocked`，不会伪造成成功。

## 安全边界

- 不读取、不输出、不写入 API key、token、连接串密码或其他 secret 原文。
- 角色输入中出现 secret-like 文本时必须阻断。
- `auto_signed=false`、`auto_approved=false`、`auto_closed=false`。
- `public_production_direct_launch=No-Go` 必须保持不变。
- 当前 Go 仅表示受控试点 Go，不代表公网生产上线批准。

## 成功判定

成功后应看到：

- `production_landing_signoff_closeout` 最新报告 `status=success`。
- `target_record_written=true`。
- `manual_signoff_record_validation` 最新报告 `status=success`。
- `production_landing_status` 最新报告 `status=success`。
- `production_landing_final_verification` 最新报告 `status=success`。
- `secret_plaintext_output=false`。
- `public_production_direct_launch=No-Go`。

## 失败恢复

- 若缺少签核人或未输入 `YES`，重新运行交互式脚本即可。
- 若签核人输入被识别为 secret-like，改用人员姓名或工号后重试。
- 若 final verification 仍为 `partial`，先查看 `production_landing_signoff_closeout` 报告中的 `missing_conditions` 和 `steps`。
- 若报告显示上游技术证据过期或缺失，重新执行 action pack 推荐命令后再重试 closeout。

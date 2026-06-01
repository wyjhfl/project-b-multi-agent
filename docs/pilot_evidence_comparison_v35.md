# v3.5 Phase 15.1 Pilot Evidence Comparison Snapshot Runbook

## 目标

在默认 fake/offline 前提下，生成一次“试点证据对比快照（baseline vs current）”，用于对比同类证据在两个时间点的覆盖度、状态与差异，服务于试点复核、发布前评审和交接审阅。

## 输入来源

- baseline manifest JSON 或证据目录（可通过 `--baseline` 指定；未指定时使用默认路径）
- current manifest JSON 或证据目录（可通过 `--current` 指定；未指定时使用默认路径）

建议将 baseline/current 指向已有的只读报告目录，例如：

- `docs/reports/acceptance_snapshots/`
- `docs/reports/demo_artifacts/`
- `docs/reports/failure_diagnostics/`
- `docs/reports/report_index/`
- `docs/reports/config_drift/`
- `docs/reports/governance_policy/`
- `docs/reports/live_drill_window/`
- `docs/reports/evidence_archive/`

## 默认输出目录

- `docs/reports/pilot_evidence_comparison/`

## 推荐命令

```powershell
python scripts/pilot_evidence_comparison.py `
  --baseline docs/reports/evidence_archive/baseline `
  --current docs/reports/evidence_archive/current `
  --output-dir docs/reports/pilot_evidence_comparison
```

```powershell
python scripts/pilot_evidence_comparison.py `
  --baseline docs/reports/evidence_archive/baseline_manifest.json `
  --current docs/reports/evidence_archive/current_manifest.json `
  --output-dir docs/reports/pilot_evidence_comparison
```

## 输出字段（建议）

- `generated_at`：生成时间（ISO8601）
- `version`：当前应用版本；v3.5 release prep 前保持 `3.4.0`
- `status`：总体状态
- `baseline_input` / `current_input`：输入 manifest 或目录路径
- `baseline_source_type` / `current_source_type`：输入类型
- `baseline_total_files` / `current_total_files`：文件数量
- `comparison`：新增、减少、变化文件的统计与明细
- `warnings`：告警列表（如空目录、类型缺失）
- `boundary_declarations`：只读与隐私边界声明
- `read_only`：固定为 `true`
- `real_llm_executed`：固定为 `false`

## 状态解释

- `success`：baseline/current 均存在且可比较，且已产出有效差异摘要。
- `skipped`：缺少 baseline 或 current，或任一目录为空，无法形成有效对比。
- `blocked`：输入条件满足但执行被明确阻断（如路径不可访问、权限不足）。
- `partial`：baseline/current 均可读取，但存在非致命告警。
- `failed`：执行异常导致结果不可用。
- `warnings`：非致命问题列表，不作为顶层状态词，例如部分类型缺失或目录结构不完整。

强约束：缺少 baseline/current 或空目录时，必须输出 `skipped` 并记录 `warnings`，不得伪造成 `success`。

## 只读边界

- 不读取报告正文内容，仅使用文件与目录元数据。
- 不删除、移动、重命名任何证据文件。
- 不自动执行 retention 清理。
- 不写入业务数据，仅写 comparison 结果文件。
- 默认 fake/offline，不执行真实外网 LLM。

## 隐私与 Secret 边界

- 不读取或输出真实 secret 原文。
- 输出中仅允许出现配置项名称或布尔状态（如 `present=true/false`），不落盘密钥值。
- 不记录 prompt 原文、不记录连接串密码原文。

## 与 evidence_archive_manifest 的关系

- `evidence_archive_manifest` 负责“证据资产盘点与索引”（清单视角）。
- `pilot_evidence_comparison` 负责“两个快照之间的差异对比”（变化视角）。
- 推荐流程：先生成/复用 manifest，再以 manifest JSON 或其对应目录作为 baseline/current 输入执行 comparison。
- comparison 不替代 manifest，二者共同构成“可审阅证据链”。

## Go/No-Go 口径

- `Go`（企业内网试点）：comparison 状态为 `success` 或可解释的 `partial`，且无越权写操作、无 secret 泄漏风险、无伪成功。
- `No-Go`：出现 `failed`/不可解释 `blocked`，或存在边界违规（读取正文、移动删除证据、输出 secret 原文、伪造 success）。
- 保持统一边界声明：不宣称公网生产可直接上线，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。

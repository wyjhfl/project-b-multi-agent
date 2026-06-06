# v4.2 Production Acceptance Gap Register（只读）

## 定位

本阶段将 Acceptance Drill Evidence Index 中的缺失域、skipped 域和 blocked 域整理为人工跟踪台账。登记册只生成责任人、到期时间、补偿控制和关闭证据槽位，不自动关闭缺口，不自动批准上线。

## 输入与输出

- 输入：`acceptance_drill_evidence_index.py` 生成的 JSON。
- 默认输出目录：`docs/reports/production_acceptance_gaps/`。
- 输出格式：JSON + Markdown。

## 状态语义

- `skipped`：未提供 index、输入不可读取或上游显式 skipped。
- `partial`：已生成缺口登记册，存在需人工跟踪的 open gap。
- `blocked`：上游 blocked/failed、检测到 secret-like 输入、非只读报告、真实执行/连接标记、release/tag 标记或自动审批/自动关闭标记。

## 只读边界

- 不读取 Markdown 报告正文。
- 不读取或输出真实 secret 原文。
- 不修改上游报告，不修改 `.env` 或环境变量。
- 不自动关闭 gap，不自动批准上线。
- 不执行真实外部系统连接或生产动作。

## 验收命令

```powershell
pytest tests/test_production_acceptance_gap_register_v423.py
```

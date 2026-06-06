# v4.2 Acceptance Drill Evidence Index（只读）

## 定位

本阶段把多轮受控生产验收演练报告纳入只读索引，便于人工比较验收覆盖域、review-ready 域数量和 blocked/skipped 状态。

## 输入与输出

- 默认输入目录：`docs/reports/controlled_production_acceptance/`。
- 默认输出目录：`docs/reports/acceptance_drill_index/`。
- 输出格式：JSON + Markdown。

## 只读边界

- 仅扫描 `*_controlled_production_acceptance_drill.json`。
- 不读取 Markdown 报告正文。
- 不读取或输出真实 secret 原文。
- 不修改、不移动、不删除输入证据。
- 不自动批准上线，不自动关闭 blocker。
- 不执行真实外部系统连接或生产动作。

## 验收命令

```powershell
pytest tests/test_acceptance_drill_evidence_index_v422.py
```

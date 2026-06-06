# v4.1 Closure Evidence Index（只读）

## 定位

本阶段把多轮 `launch_blocker_closure_workflow.py` 输出纳入只读索引，便于人工复核 closure evidence 的演进状态。索引只读取 closure workflow JSON 的结构化元数据，不读取 Markdown 正文，不展开证据报告内容。

## 输入与输出

- 默认输入目录：`docs/reports/launch_blocker_closure/`。
- 默认输出目录：`docs/reports/closure_evidence_index/`。
- 输出格式：JSON + Markdown。

## 状态语义

- `skipped`：输入目录缺失、不是目录或没有可索引的 closure workflow JSON。
- `partial`：已索引 closure workflow JSON；该状态不代表生产 Go，只代表索引生成完成并可进入人工复核。
- `blocked`：检测到 secret-like 输入、非只读报告、自动审批/自动关闭标记、上游 blocked/failed。

## 只读边界

- 不读取 Markdown 报告正文。
- 不读取或输出真实 secret 原文。
- 不修改、不移动、不删除输入证据。
- 不自动关闭 blocker，不自动批准上线。
- 不执行真实 LLM、真实外部系统连接、部署、迁移、发布、回滚、压测、备份恢复、安全扫描、审计导出、密钥轮换或权限变更。

## 验收命令

```powershell
pytest tests/test_closure_evidence_index_v412.py
```

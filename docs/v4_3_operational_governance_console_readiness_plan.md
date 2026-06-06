# v4.3 Operational Governance Console Readiness 规划

## 定位

v4.3 将 v4.1/v4.2 的上线阻断、关闭证据、人工签核、受控生产验收和验收缺口入口纳入只读运营治理视图。默认不触发真实外部系统，不读取报告正文，不执行清理、审批或关闭动作。

## Phase 23.1：Operations summary v4 evidence entry（已完成）

### 目标

增强 `/operations/summary` 的 `observability` 元数据，纳入 v4.1/v4.2 证据 runbook 与默认报告目录计数，便于运营台只读展示。

### 交付物

- 后端只读 summary 增强：`app/api/operations.py`
- 回归测试：`tests/test_operations_summary_v312.py`

### 边界

- 仅统计 JSON 报告数量，不读取报告正文。
- 不连接真实 LLM/MCP/IdP/业务系统/数据库/Redis/APM/日志/告警。
- 不自动批准上线，不自动关闭 blocker/gap。
- 不删除、不移动、不清理报告。

## Phase 23.2：Frontend v4 evidence read-only view（已完成）

### 目标

增强前端 `/operations` 页面，展示 `observability.v4_evidence` 的模式、边界、总 JSON 报告数和各证据入口的 runbook/目录计数。

### 交付物

- 前端类型契约：`frontend/src/types/api.ts`
- 前端只读页面：`frontend/src/app/operations/page.tsx`

### 边界

- 页面只展示后端聚合的结构化元数据，不读取报告正文。
- 不新增生成、删除、清理、审批、关闭 blocker/gap 或触发验收的按钮。
- 不触发真实 LLM，不连接真实外部系统，不输出 secret 原文。

## Phase 23.3：Operations governance empty/status semantics polish（已完成）

### 目标

增强 `/operations` 的 v4 evidence 空态和状态语义展示，避免把 JSON 报告计数、`partial` 或 `success` 误读为生产上线批准。

### 交付物

- 前端只读页面：`frontend/src/app/operations/page.tsx`

### 边界

- `metadata_available` 仅表示目录中存在 JSON 元数据，不代表验收通过。
- `skipped` 表示缺少输入或 opt-in 条件，不伪造成成功。
- `blocked` 表示边界违规、上游失败、secret-like 输入或不安全执行标记，公网生产直上仍为 No-Go。
- `partial` 表示需要人工复核，不自动批准上线。
- `success` 仅代表本地脚本完成其有限检查，不等于生产验收完成。

## Phase 23.4：v4.3.0 release prep（已完成）

### 目标

完成 v4.3.0 tag 前本地 release prep，同步版本号、release notes、release review 和最终复核材料。本轮不自动打 tag，不创建 GitHub Release。

### 交付物

- 版本同步：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、相关测试断言。
- Release notes：`RELEASE_NOTES_v4.3.0.md`
- Release review：`docs/release_review_v4.3_operational_governance_console_readiness.md`

### 边界

- 不打 `v4.3.0` tag。
- 不创建 GitHub Release。
- 不移动、删除或重建历史 tag。
- 不执行真实外部系统连接、真实 LLM、真实发布、真实回滚或生产变更。
- 不宣称真实生产验收完成，不宣称公网生产可直接上线。

## 后续 Phase 建议

- 进入 `v4.3.0` tag 前最终人工复核。
- 后续可进入 v4.4 或下一阶段生产验收证据闭环规划。

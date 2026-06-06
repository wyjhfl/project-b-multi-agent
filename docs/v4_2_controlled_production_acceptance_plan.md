# v4.2 Controlled Production Acceptance Drills 规划

## 定位

v4.2 承接 v4.1 Evidence Execution & Closure Pack，建立受控生产验收演练包。默认仍为 fake/offline，只消费脱敏证据，不执行真实外部连接或生产动作。

## Phase 22.1：Controlled production acceptance drill（P0，当前已完成）

### 目标

覆盖 real LLM、OIDC/SSO、external MCP、PostgreSQL、Redis、业务系统、APM/logging/alerting、backup/restore/DR、capacity/load/soak、security/compliance、release/rollback gate 等生产验收域，生成可人工复核的只读验收演练报告。

### 交付物

- runbook：`docs/controlled_production_acceptance_drill_v42.md`
- 只读脚本：`scripts/controlled_production_acceptance_drill.py`
- 测试：`tests/test_controlled_production_acceptance_drill_v421.py`
- 默认输出目录：`docs/reports/controlled_production_acceptance/`

### 边界

- 不连接真实外部系统。
- 不执行真实生产验收动作。
- 不读取或输出真实 secret 原文。
- 不自动批准上线。
- 不自动关闭 blocker。
- 不宣称真实生产验收完成。

## Phase 22.2：Acceptance drill evidence index（P1，当前已完成）

### 目标

将多轮受控生产验收演练报告纳入只读索引，便于人工比较验收覆盖域、review-ready 域数量和 blocked/skipped 状态。

### 交付物

- runbook：`docs/acceptance_drill_evidence_index_v42.md`
- 只读脚本：`scripts/acceptance_drill_evidence_index.py`
- 测试：`tests/test_acceptance_drill_evidence_index_v422.py`
- 默认输出目录：`docs/reports/acceptance_drill_index/`

### 边界

- 不读取 Markdown 报告正文。
- 不修改、不移动、不删除输入证据。
- 不自动批准上线。
- 不自动关闭 blocker。
- 不读取或输出真实 secret 原文。

## Phase 22.3：Production acceptance gap register（P1，当前已完成）

### 目标

将 Acceptance Drill Evidence Index 中的缺失域、skipped 域和 blocked 域整理为人工跟踪台账。

### 交付物

- runbook：`docs/production_acceptance_gap_register_v42.md`
- 只读脚本：`scripts/production_acceptance_gap_register.py`
- 测试：`tests/test_production_acceptance_gap_register_v423.py`
- 默认输出目录：`docs/reports/production_acceptance_gaps/`

### 边界

- 不读取 Markdown 报告正文。
- 不修改上游报告。
- 不自动关闭 gap。
- 不自动批准上线。
- 不读取或输出真实 secret 原文。

## 后续 Phase 建议

- Phase 22.4：v4.2 release prep，仅在用户确认后同步版本和 release notes/review，不自动 tag 或创建 GitHub Release。

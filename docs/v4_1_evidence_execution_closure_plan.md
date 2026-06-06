# v4.1 Evidence Execution & Closure Pack 规划

## 定位

v4.1 承接 v4.0 Production Launch Readiness Review，将上线阻断项从“登记与汇总”推进到“证据关闭工作流”。本阶段仍保持默认 fake/offline，不连接真实外部系统，不宣称生产上线完成。

## Phase 21.1：Launch blocker closure workflow（P0，当前实施）

### 目标

基于 v4.0 Launch Blocker Register 生成只读关闭工作流，识别每个 blocker 的 owner、到期时间、补偿控制、关闭证据、reviewer 与审批状态是否足够进入人工复核。

### 交付物

- runbook：`docs/launch_blocker_closure_workflow_v41.md`
- 只读脚本：`scripts/launch_blocker_closure_workflow.py`
- 测试：`tests/test_launch_blocker_closure_workflow_v411.py`
- 默认输出目录：`docs/reports/launch_blocker_closure/`

### 边界

- 不自动关闭 blocker。
- 不自动批准上线。
- 不伪造人工审批。
- 不读取或输出真实 secret 原文。
- 不执行真实 LLM、MCP、IdP、业务系统、数据库、Redis、APM、日志、告警、KMS、Vault、云平台或生产发布动作。

## Phase 21.2：Closure evidence index（P1，当前已完成）

### 目标

把多轮 Launch blocker closure workflow 输出纳入只读索引，便于人工复核 closure evidence 的演进状态。

### 交付物

- runbook：`docs/closure_evidence_index_v41.md`
- 只读脚本：`scripts/closure_evidence_index.py`
- 测试：`tests/test_closure_evidence_index_v412.py`
- 默认输出目录：`docs/reports/closure_evidence_index/`

### 边界

- 不读取 Markdown 报告正文。
- 不修改、不移动、不删除输入证据。
- 不自动清理报告。
- 不自动关闭 blocker。
- 不自动批准上线。
- 不读取或输出真实 secret 原文。

## Phase 21.3：Manual signoff package（P1，当前已完成）

### 目标

基于 Closure Evidence Index 生成供 CAB / release review 人工复核使用的脱敏签核包。

### 交付物

- runbook：`docs/manual_signoff_package_v41.md`
- 只读脚本：`scripts/manual_signoff_package.py`
- 测试：`tests/test_manual_signoff_package_v413.py`
- 默认输出目录：`docs/reports/manual_signoff_package/`

### 边界

- 不自动签核。
- 不自动批准上线。
- 不自动关闭 blocker。
- 不读取 Markdown 报告正文。
- 不读取或输出真实 secret 原文。
- 不执行真实发布、回滚、外部系统连接或生产变更。

## 后续 Phase 建议

- Phase 21.4：v4.1 release prep，仅在用户确认后同步版本和 release notes/review，不自动 tag 或创建 GitHub Release。

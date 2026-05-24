# v0.4 第五阶段：追加式审计日志设计

## AuditEvent 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| event_id | str | 事件唯一 ID（uuid4） |
| event_type | str | 事件类型（见下表） |
| timestamp | datetime | 事件时间（UTC） |
| actor | str | 执行者（system / user_id / agent） |
| task_id | str | 关联任务 ID |
| approval_id | str \| None | 关联审批 ID |
| tool_name | str \| None | 关联工具名称 |
| action | str | 动作描述 |
| outcome | str | 结果：success / blocked / failed / approved / rejected |
| reason | str \| None | 原因 |
| severity | str \| None | 严重级别：info / warn / high / critical |
| detail | dict | 附加详情（matched_patterns / error_type / mode 等） |

## 必须写审计的事件

| event_type | 触发时机 | outcome | severity |
|------------|---------|---------|----------|
| prompt_injection_blocked | query/payload 注入被拦截 | blocked | high |
| prompt_injection_detected | 注入被检测但只 warn | success | warn |
| operation_whitelist_blocked | 操作不在白名单 | blocked | high |
| approval_payload_tampered | resume payload 被篡改 | blocked | critical |
| resume_blocked_by_policy | resume 被策略阻止 | blocked | high |
| approval_requested | 高风险操作请求审批 | success | info |
| approval_approved | 审批通过 | approved | info |
| approval_rejected | 审批拒绝 | rejected | warn |
| approval_resume_started | 恢复执行开始 | success | info |
| approval_resume_completed | 恢复执行完成 | success | info |
| approval_resume_failed | 恢复执行失败 | failed | warn |
| task_cancelled | 任务被取消 | failed | warn |

## 审计日志与 TraceRecorder 的区别

| 维度 | TraceRecorder | AuditEvent |
|------|--------------|------------|
| 目的 | 执行链路观察、调试、性能分析 | 合规审计、不可变、谁在何时做了什么 |
| 生命周期 | 任务级，可随任务删除 | 永久保留，append-only |
| 粒度 | 细粒度（每步工具调用） | 粗粒度（安全事件 + 审批决策） |
| 不可变性 | 可被测试重置 | 不可变、不可删除 |
| 查询 | 按 task_id 查事件列表 | 按 event_type / actor / 时间范围 / outcome 查询 |
| 存储 | 内存（TraceRecorder） | SQLiteAuditStore（持久化） |

## v0.4 第五阶段实现计划

1. 新增 `app/storage/audit_store.py`：SQLiteAuditStore
   - `append(event: AuditEvent)` → 写入审计事件
   - `query(event_type, actor, task_id, outcome, start_time, end_time, limit)` → 查询审计事件
   - 表 `audit_events`，append-only，无 update/delete

2. 新增 `app/models/schemas.py` 扩展：AuditEvent 模型（已有基础定义）

3. 接入点：
   - 各 API 端点的安全事件写入审计
   - ApprovalStore 决策写入审计
   - ApprovalResumeService resume 结果写入审计

4. API：
   - GET /audit/events → 查询审计事件
   - GET /audit/events/{event_id} → 单条审计事件

5. 测试：
   - prompt injection blocked 写入审计
   - approval approved/rejected 写入审计
   - 审计事件不可删除

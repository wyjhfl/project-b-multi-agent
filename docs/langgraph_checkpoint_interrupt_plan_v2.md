# LangGraph Checkpoint / Interrupt / Resume Plan v2

## 0. 规划结论

Phase 2 推荐采用 **adapter-first** 路线：先新增持久化 checkpoint 基座，再把现有 Harness Runtime 的 HITL 审批流映射到 LangGraph interrupt / resume。不要重写 `AgentKernel`、不要替换 `ApprovalResumeService`，而是让它们在发现 graph checkpoint 时走 graph resume 适配器；没有 checkpoint 时继续走 v2.0.1 的兼容恢复逻辑。

本文件只定义设计与实施计划，不创建迁移、不改代码、不改变 v2.0.1 行为。

## 1. 当前状态审查

### 1.1 当前 HITL approval / reject / resume 如何工作

当前 HITL 是 Harness 业务层审批，不是 LangGraph 原生 interrupt：

1. `/tasks` 创建 `TaskRun`，调用 `AgentKernel.run_with_options()`。
2. keyword 模式下，`AgentKernel.run()` 执行：
   - `ContextAssembler` 组装上下文；
   - `KeywordPlanner` 选择工具；
   - `_execute()` 读取 `ToolGateway` 的 `ToolSpec`；
   - `PolicyEngine.evaluate(tool_name, risk_level=spec.risk_level)` 判断风险。
3. `PolicyEngine.check()` 对 `RiskLevel.high` 返回不允许；`evaluate()` 返回：
   - `allowed=false`；
   - `requires_approval=true`；
   - `reason="高风险工具 ... 需要人工审批"`。
4. `_execute()` 如果发现 `requires_approval` 且存在 `approval_store`：
   - 调用 `ApprovalStore.create_approval()` 创建审批单；
   - payload 保存 `mode=query/tool_name/arguments/plan_result` 等恢复所需业务字段；
   - 记录 `approval_requested` trace；
   - 将 task 标记为 `waiting_approval`；
   - 返回 `requires_approval=true` 和 `approval_id`。
5. multitool 模式下，`MultiToolPipeline` 在高风险 step 处创建审批并返回 `requires_approval`；`AgentKernel._run_multitool()` 将 task 标记为 `waiting_approval`。
6. `/approvals/{id}/approve`：
   - 调用 `ApprovalStore.decide_approval(... approved=True ...)`；
   - 记录 `approval_approved` trace 和 audit；
   - 默认 `auto_resume=true` 时调用 `_do_resume()`。
7. `/approvals/{id}/reject`：
   - 调用 `ApprovalStore.decide_approval(... approved=False ...)`；
   - 记录 `approval_rejected` trace 和 audit；
   - 调用 task store 将任务更新为 `cancelled`。
8. `/approvals/{id}/resume` 或 approve 的 auto resume：
   - 构造 `ApprovalResumeService`；
   - 调用 `resume(approval_id)`；
   - 根据 approval payload 的 `mode` 走 keyword 或 multitool 恢复。

### 1.2 当前 ApprovalResumeService 的职责

`ApprovalResumeService` 是当前业务级恢复执行器，主要职责是：

- 校验 approval 是否存在、是否已 approved。
- 基于 approval payload 的 `resumed` 字段实现幂等返回。
- 使用 `OperationWhitelist.check_payload_integrity()` 校验审批 payload 没被篡改。
- keyword 恢复：调用被批准的工具，更新 task 为 `completed` 或 `failed`。
- multitool 恢复：
  - 解析已完成 step、变量依赖和待恢复 step；
  - 执行被批准 step；
  - 继续执行后续低风险 step；
  - 如果后续又遇到高风险 step，则创建新 approval，并将 task 继续置为 `waiting_approval`。
- 写入恢复结果：`resumed`、`resume_status`、`resume_result`、`approval_consumed`、`resume_attempt_count`、`last_resume_error` 等。
- 写 trace / audit：如 `approval_resume_started`、`approval_resume_completed`、`multitool_resume_waiting_approval`。

边界：它现在是“重放/继续业务步骤”的 service，不知道 LangGraph checkpoint、thread id、current node，也不调用 graph-native resume。

### 1.3 当前 AgentKernel.build_graph() 的真实能力边界

`AgentKernel.build_graph()` 当前只是最小 LangGraph smoke graph：

- 节点：`assemble_context -> plan -> execute -> verify -> respond`。
- 每个节点只修改 `state["stage"]`。
- 编译后仅用于 `get_graph_summary()` 展示节点和边。
- 当前真实任务执行仍走 `run()` / `run_with_options()` 内的 Python 顺序流。
- 没有 checkpointer、没有 thread/config、没有 interrupt、没有 graph-native resume。
- 现有测试 `tests/test_langgraph_kernel_v11.py` 只验证 graph summary 和 keyword API 不变。

所以当前“LangGraph 已接入”的实际含义是：框架依赖和最小图结构存在，但生产执行链路尚未使用 LangGraph 状态机。

### 1.4 当前 task / approval / trace / audit / metrics 数据流

- task：
  - `/tasks` 创建内存 `TaskRun`；
  - `AgentKernel` 更新状态和 result；
  - API 末尾调用 `TaskStore.save_task(task, mode=req.mode)`；
  - reject / resume 通过 `TaskStore.update_task_status()` 更新状态。
- approval：
  - 高风险工具或多工具 step 调用 `ApprovalStore.create_approval()`；
  - approve / reject 调用 `decide_approval()`；
  - resume 通过 `update_payload()` 写恢复状态和幂等字段。
- trace：
  - `TraceRecorder` 记录任务开始、计划、工具调用、审批请求、恢复、失败等事件；
  - `/tasks/{task_id}/trace` 读取 trace。
- audit：
  - 审批决策、恢复、payload 篡改、prompt injection 等写 `AuditRecorder`；
  - `/audit/events` 读取审计事件。
- metrics：
  - `AgentKernel._record_task_metrics()` 在各 mode 执行后写运行指标；
  - tool / token 指标由对应 recorder/store 写入；
  - `/metrics/*` 读取 runtime metrics。

Phase 2 的 checkpoint 不应替代上述流，而应补充 graph state 的持久化与恢复坐标。

### 1.5 当前 PostgreSQL Store Factory 能为 Phase 2 提供什么

v2.0.1 已完成 Store Factory 主链路：

- `app.storage.factory.get_task_store()` 根据 `settings.storage_backend` 和 `settings.database_url` 返回 SQLite 或 PostgreSQL TaskStore。
- approval / audit / metrics 同理。
- `app.main` getter 已接入 factory，`reset_runtime_for_test()` 后会按当前配置重建 store。
- 默认仍是 `storage_backend=sqlite`；企业试点通过 `STORAGE_BACKEND=postgres` + `DATABASE_URL` 启用 PostgreSQL。

这为 Phase 2 提供了可复用模式：新增 `GraphCheckpointStore` 时也应通过 factory 切换 SQLite / PostgreSQL，不改变默认兼容行为。

## 2. 当前差距

### 2.1 当前 resume 为什么还不是 LangGraph 原生 resume

当前 resume 是 `ApprovalResumeService` 根据 approval payload 再调用工具或继续执行 multitool step：

- 没有从 LangGraph checkpointer 读取图状态。
- 没有保存或恢复 graph thread/config。
- 没有从中断节点继续执行，而是用业务 payload 重构恢复上下文。
- 没有 graph-native command / resume payload 映射。
- 服务重启后只能依赖 approval/task 表里的业务字段，无法恢复图运行栈和节点状态。

### 2.2 当前 approval 为什么还不是 LangGraph interrupt

当前 approval 是策略层“拦截后创建审批单”：

- `PolicyEngine` 返回 `requires_approval`，但没有调用 LangGraph interrupt。
- `AgentKernel._execute()` 和 `MultiToolPipeline` 直接 return `requires_approval`，不是 graph 暂停。
- approval payload 是业务恢复输入，不是 interrupt payload。
- 审批通过后没有将 resume command 送回 graph。

### 2.3 当前 checkpoint 缺哪些持久化字段

现有 `task_runs` 和 `approval_requests` 缺少 graph-native 恢复所需字段：

- `checkpoint_id`：唯一 checkpoint 标识。
- `graph_thread_id` / `run_id`：LangGraph thread 或运行实例标识。
- `task_id` 与 `approval_id` 的关联坐标。
- `graph_state`：序列化后的图状态。
- `current_node` / next nodes：中断或恢复位置。
- `pending_interrupt`：中断原因、风险、工具、参数、审批上下文。
- `resume_payload`：审批通过后输入 graph 的恢复数据。
- `consumed` / `resumed_at`：防重复恢复。
- `expires_at`：过期 checkpoint 清理。
- `version` / `schema_version`：后续演进兼容。
- 并发控制字段：如 `locked_by`、`locked_at`、`resume_attempt_count` 或 optimistic version。

### 2.4 并发恢复、重复 resume、过期 checkpoint 风险

- 并发恢复：两个 approve/resume 请求可能同时读取未 consumed checkpoint 并重复执行工具。
- 重复 resume：当前 approval payload 有 `resumed`，但不是数据库原子 compare-and-set；高并发下仍需 store 层原子消费。
- 过期 checkpoint：如果审批长期未处理，工具参数、上下文、权限或数据版本可能失效。
- 半成功状态：graph resume 执行工具成功但写 checkpoint/approval payload 失败，会造成审计与状态不一致。
- 后续高风险 step：一个 resume 过程中再次 interrupt，需要明确旧 approval consumed、新 approval pending、task 继续 waiting 的关系。

## 3. 推荐架构

### 3.1 总体原则

推荐架构：**新增 checkpoint substrate + graph adapter，保留 Harness Runtime 业务组件**。

- 保留 `AgentKernel.run_with_options()` 对外入口，先用配置开关或 mode 内部切换到 graph runtime。
- 保留现有 `ApprovalStore` 作为人工审批事实来源。
- 保留 `ApprovalResumeService` 作为 `/approvals/{id}/resume` 兼容 facade。
- 新增 graph checkpoint/state 层，只在 Phase 2 graph runtime 启用。
- SQLite 默认兼容；PostgreSQL 企业试点模式支持持久化恢复。

### 3.2 LangGraph checkpoint 如何接入现有 Harness Runtime

建议引入一个薄适配层：`GraphRuntimeAdapter`。

职责：

- 将现有 Harness 节点映射为 graph node：
  - `assemble_context` 调用现有 `ContextAssembler`；
  - `plan` 调用现有 planner / mode router；
  - `execute` 仍通过 `ToolGateway`；
  - `verify` / `respond` 复用现有逻辑；
  - trace / audit / metrics 继续调用现有 recorder。
- 每次关键节点结束后通过 `GraphCheckpointStore` 保存 graph state。
- 发生高风险操作时生成 interrupt payload，创建 approval，并保存 pending checkpoint。
- 审批通过后读取 checkpoint，构造 resume payload，继续 graph。

`AgentKernel` 的修改应限于适配入口和依赖注入，不重写现有顺序流。默认配置下继续执行 v2.0.1 顺序流。

### 3.3 interrupt 触发点

Phase 2 先覆盖现有高风险语义，不扩大权限模型：

1. `PolicyEngine` high risk：
   - 当前 `RiskLevel.high` 返回 `requires_approval`；
   - Phase 2 graph node 中将该结果转为 interrupt payload。
2. `ToolGateway` high-risk tool：
   - 执行工具前读取 `ToolSpec.risk_level`；
   - 如果为 high，则 graph 暂停，不调用工具。
3. `RiskIntentGuard` 或危险操作意图：
   - MultiAgent eval 前置高风险意图检测已有基础；
   - Phase 2 可把危险意图结果写入 interrupt payload，作为“不绑定具体工具”的审批原因。

不建议 Phase 2 首轮把所有 medium risk 都 interrupt；保持 v2.0.1 风险语义稳定。

### 3.4 approve / reject / resume 与 graph resume 的映射

- approve：
  - `ApprovalStore.decide_approval(... approved=True ...)` 仍是审批事实；
  - 如果 approval payload 含 `checkpoint_id`，`ApprovalResumeService.resume()` 委托 `GraphResumeAdapter.resume(checkpoint_id, approval_id)`；
  - 如果没有 `checkpoint_id`，继续走当前 keyword/multitool legacy resume。
- reject：
  - approval 置为 `rejected`；
  - checkpoint 置为 `cancelled` 或 `consumed=true`，`resume_payload={"decision":"rejected"}`；
  - task 置为 `cancelled`；
  - 不继续 graph 执行。
- resume：
  - 用 `checkpoint_id` 原子 claim checkpoint；
  - 校验 approval 已 approved、checkpoint 未 consumed、未过期；
  - 构造 LangGraph resume command / resume payload；
  - graph 从 `current_node` 后继续；
  - 成功后写 `resumed_at`、`consumed=true`、task final status；
  - 如果再次 interrupt，旧 checkpoint consumed，新 checkpoint pending，新 approval pending，task 保持 `waiting_approval`。

### 3.5 保留组件

Phase 2 应保留并复用：

- `ApprovalStore`：审批单创建、决策、列表、payload 更新。
- `ApprovalResumeService`：API 兼容 facade、legacy resume、graph resume 分流。
- `AuditRecorder`：审批、恢复、中断、拒绝、异常的审计事实。
- `TraceRecorder`：graph node、checkpoint、interrupt、resume 的运行轨迹。
- `RuntimeMetricsRecorder`：任务耗时、工具调用、resume 次数、checkpoint 恢复结果指标。
- `PolicyEngine` / `OperationWhitelist`：现有高风险与白名单语义。
- `ToolGateway`：工具注册和调用入口。

### 3.6 新增组件

建议新增：

- `GraphCheckpointStore` 接口：
  - `create_checkpoint(state)`；
  - `get_checkpoint(checkpoint_id)`；
  - `get_latest_for_task(task_id)`；
  - `mark_pending_interrupt(checkpoint_id, approval_id, payload)`；
  - `claim_for_resume(checkpoint_id, approval_id)`；
  - `mark_resumed(checkpoint_id, resume_payload, result)`；
  - `mark_cancelled(checkpoint_id, reason)`；
  - `expire_old(now)`。
- `GraphRunState` model：统一 task、approval、checkpoint、current_node、graph_state。
- `InterruptPayload` schema：稳定描述中断原因、风险、工具、参数、policy decision、trace ids。
- `GraphResumeAdapter`：把 approval decision 映射为 graph resume command。
- `checkpoint_id` / resume token 机制：approval payload 保存 `checkpoint_id`，可选保存不可猜测 `resume_token_hash`，API 不暴露明文 token。

### 3.7 只做适配、不重写的组件

- `AgentKernel`：只新增 graph runtime adapter 调用点；保留 keyword / nl2sql / multitool / auto 旧路径。
- `ApprovalResumeService`：只新增 checkpoint 分支；legacy 逻辑不重写。
- `PolicyEngine`：只把现有 decision 转为 interrupt，不改变 RBAC 或风险语义。
- `ToolGateway`：不改变工具注册/调用协议；只在 graph execute node 读取风险并决定是否 interrupt。
- API：保持路径和响应兼容，仅增加可选字段。

## 4. 数据模型设计

### 4.1 建议新增表：graph_run_states

建议新增独立表，不把所有 graph 字段塞进 `task_runs` 或 `approval_requests`，避免破坏现有 store 返回结构。

字段草案：

- `checkpoint_id` TEXT / UUID，主键。
- `task_id` TEXT，索引，关联 `task_runs.task_id`。
- `approval_id` TEXT nullable，索引，关联当前 pending approval。
- `graph_thread_id` TEXT，LangGraph thread/config 坐标。
- `run_id` TEXT nullable，一次执行尝试标识。
- `status` TEXT：`running | interrupted | resumed | completed | cancelled | expired | failed`。
- `current_node` TEXT：当前或即将恢复节点。
- `graph_state` JSON/TEXT：序列化图状态。
- `pending_interrupt` JSON/TEXT nullable：interrupt payload。
- `resume_payload` JSON/TEXT nullable：审批后恢复输入。
- `result_snapshot` JSON/TEXT nullable：恢复或完成后的结果摘要。
- `consumed` BOOLEAN：是否已被 resume/reject 消费。
- `resumed_at` DATETIME nullable。
- `created_at` DATETIME。
- `updated_at` DATETIME。
- `expires_at` DATETIME nullable。
- `schema_version` INTEGER，默认 1。
- `resume_attempt_count` INTEGER，默认 0。
- `last_resume_error` TEXT nullable。
- `locked_by` TEXT nullable。
- `locked_at` DATETIME nullable。

最小必需字段覆盖用户要求：`checkpoint_id`、`task_id`、`approval_id`、`graph_state`、`current_node`、`pending_interrupt`、`resume_payload`、`consumed`、`resumed_at`、`created_at`、`updated_at`、`expires_at`。

### 4.2 interrupt payload schema

建议稳定为 JSON object：

```json
{
  "schema_version": 1,
  "interrupt_type": "tool_approval",
  "task_id": "...",
  "checkpoint_id": "...",
  "node": "execute",
  "mode": "keyword|multitool|auto|multi_agent",
  "tool_name": "refund_order",
  "arguments": {},
  "risk_level": "high",
  "permission_scope": "write|admin|schema",
  "policy_decision": {
    "allowed": false,
    "requires_approval": true,
    "reason": "..."
  },
  "agent_reason": "...",
  "trace_context": {
    "event_id": "..."
  },
  "created_at": "ISO-8601"
}
```

危险意图但尚未绑定工具时：`interrupt_type="risk_intent"`，`tool_name=null`，`arguments={}`，保留 `risk_intent` 字段。

### 4.3 SQLite fallback 策略

- 新增 `app/storage/graph_checkpoint_store.py` 实现 SQLite 版本。
- 数据库文件沿用当前本地 data/db 策略。
- JSON 字段以 TEXT 存储，读写时 `json.dumps(... ensure_ascii=False)` / `json.loads()`。
- 幂等 claim 使用单 SQL 条件更新：`WHERE checkpoint_id=? AND consumed=0 AND status='interrupted'`，避免重复 resume。
- 默认 `storage_backend=sqlite` 时所有旧 API 不需要 PostgreSQL。

### 4.4 PostgreSQL 实现策略

- 新增 `app/storage/postgres/graph_checkpoint_store.py`。
- SQLAlchemy model 使用 JSONB 或 JSON 字段；PostgreSQL 优先 JSONB。
- `claim_for_resume()` 使用事务和条件更新；必要时使用 `SELECT ... FOR UPDATE`。
- 索引：
  - `checkpoint_id` primary key；
  - `task_id`；
  - `approval_id`；
  - `(status, expires_at)`；
  - `(task_id, created_at desc)`。
- Store Factory 新增 `get_graph_checkpoint_store()`，遵循现有 sqlite/postgres 切换规则。

### 4.5 Alembic 迁移计划

Phase 2.1 创建迁移，但本规划阶段不创建迁移文件。

迁移内容：

- 新建 `graph_run_states` 表。
- 添加上述字段、索引和默认值。
- 不修改 `task_runs`、`approval_requests` 既有字段，降低回归风险。
- 迁移 downgrade 删除索引和表。
- Docker startup migration 继续由 `scripts/start_app.py` 执行 `alembic upgrade head`。

## 5. API 兼容策略

### 5.1 /tasks 是否需要新增参数

短期不要求新增参数。Phase 2 初期建议通过配置开关启用 graph runtime，例如：

- `graph_runtime_enabled=false` 默认关闭；
- 或内部按 mode 白名单启用。

如果后续需要调试，可在 `/tasks` 增加可选参数 `graph_runtime: bool | None = None`，但默认 `None` 表示跟随配置，旧调用无需变更。

### 5.2 /approvals/{id}/resume 保持兼容

必须保持兼容：

- 旧 approval payload 没有 `checkpoint_id`：继续走当前 `ApprovalResumeService` legacy resume。
- 新 approval payload 有 `checkpoint_id`：走 graph resume adapter。
- 响应继续包含现有字段：`resumed` / `already_resumed` / `approval_id` / `task_id` / `resume_result`。
- 可追加字段：`checkpoint_id`、`graph_resumed`、`resume_status`，但不删除旧字段。

### 5.3 是否新增 graph-state 查询 API

建议新增只读调试 API，但放到 Phase 2.4 或 2.5：

- `GET /tasks/{task_id}/graph-state`：返回最新 checkpoint 摘要、status、current_node、approval_id、expires_at。
- 可选 `GET /tasks/{task_id}/checkpoint` 作为别名，但推荐只保留一个正式路径，避免 API 冗余。
- 权限沿用 `tasks:read`。
- 默认 graph runtime 未启用时返回 `{ "enabled": false }` 或 `{ "checkpoint": null }`，不影响旧 API。

### 5.4 默认配置下旧 API 如何不受影响

- `auth_enabled=false` / `rbac_enabled=false` 默认不变。
- `storage_backend=sqlite` 默认不变。
- `graph_runtime_enabled=false` 初始默认关闭。
- `/tasks`、`/approvals`、`/audit`、`/metrics` 旧响应字段不删除。
- 旧 HITL 测试继续覆盖 legacy resume，新增 graph tests 不应改变旧断言。

## 6. 测试计划

### 6.1 单元测试

新增测试文件建议：

- `tests/test_graph_checkpoint_store_v21.py`
  - SQLite create/get checkpoint。
  - `get_latest_for_task()` 返回最新 checkpoint。
  - `claim_for_resume()` 第一次成功、第二次失败。
  - expired checkpoint 不能 claim。
- `tests/test_graph_interrupt_payload_v21.py`
  - high-risk tool interrupt payload 字段完整。
  - dangerous intent interrupt payload 支持 `tool_name=null`。
  - payload schema version 缺失或非法时校验失败。
- `tests/test_graph_resume_idempotency_v21.py`
  - 同一 `checkpoint_id` 重复 resume 不重复调用工具。
  - approval 已 `resumed` 时返回 cached result。
  - checkpoint consumed 后再次 resume 返回 `already_resumed`。

### 6.2 集成测试

新增集成测试建议：

- high risk task -> graph interrupt -> approval created：
  - task status 为 `waiting_approval`；
  - approval payload 包含 `checkpoint_id`；
  - graph checkpoint status 为 `interrupted`。
- approve -> graph resume -> task completed：
  - approve 后调用 resume；
  - graph 从 checkpoint 后继续；
  - task status 为 `completed`；
  - checkpoint `consumed=true`、`resumed_at` 非空。
- reject -> task cancelled：
  - approval rejected；
  - task status 为 `cancelled`；
  - checkpoint status 为 `cancelled`。
- repeated resume -> no duplicate execution：
  - 工具 call_count 保持 1；
  - 第二次 resume 返回 `already_resumed`。
- server restart -> checkpoint restored：
  - 创建 interrupted checkpoint 后重置 runtime；
  - 重新构造 store/kernel；
  - resume 能读取 checkpoint 并完成任务。

### 6.3 回归测试

必须持续运行：

- `tests/test_hitl_v04.py`：原有 HITL approval/reject 基线继续通过。
- `tests/test_approval_resume_v042.py`：legacy resume 行为继续通过。
- `tests/test_v043_full_resume.py`：多工具完整 resume、后续高风险 step、幂等与失败路径继续通过。
- `tests/test_langgraph_kernel_v11.py`：当前 graph summary 和 keyword API 不变。
- `/tasks` 成功流程继续通过。
- SQLite 默认模式继续通过。
- PostgreSQL 配置模式在 `storage_backend=postgres` + `database_url` 下通过。

## 7. 分阶段实施路线

### Phase 2.1：Checkpoint Store + schema + tests

修改/新增文件：

- 新增 `app/storage/graph_checkpoint_store.py`。
- 新增 `app/storage/postgres/graph_checkpoint_store.py`。
- 修改 `app/storage/models.py` 增加 `GraphRunStateRow`。
- 修改 `app/storage/factory.py` 增加 `get_graph_checkpoint_store()`。
- 新增 Alembic revision：创建 `graph_run_states`。
- 新增 `tests/test_graph_checkpoint_store_v21.py`。

验收标准：

- SQLite / PostgreSQL store CRUD 行为一致。
- `claim_for_resume()` 原子幂等。
- 过期 checkpoint 不能被恢复。
- 旧 storage/auth/rbac 测试继续通过。

风险：

- JSON 序列化兼容性。
- SQLite 与 PostgreSQL 并发语义不一致。
- Alembic migration 与 Docker startup migration 兼容。

### Phase 2.2：AgentKernel graph state adapter

修改/新增文件：

- 新增 `app/agent/graph/runtime_adapter.py`。
- 新增 `app/agent/graph/state.py`。
- 最小修改 `app/agent/graph/kernel.py`：注入 adapter，配置开启时委托 graph runtime。
- 修改 `app/main.py`：构造 checkpoint store 和 adapter。
- 新增 `tests/test_graph_runtime_adapter_v22.py`。

验收标准：

- graph runtime 关闭时，旧 `run_with_options()` 完全不变。
- graph runtime 开启时，低风险 keyword task 可完成并写 checkpoint。
- trace / metrics 仍按旧 recorder 写入。

风险：

- 真实执行链路与现有顺序流出现分叉。
- graph state 与 `TaskRun.result` 字段映射不完整。
- 当前 `build_graph()` smoke graph 需要升级但不能破坏 v1.1 测试。

### Phase 2.3：interrupt 触发与 approval 映射

修改/新增文件：

- 新增 `app/agent/graph/interrupts.py`。
- 修改 `app/agent/graph/runtime_adapter.py`：高风险 decision 转 interrupt。
- 修改 `app/services/multitool_pipeline.py` 或通过 adapter 包装其 high-risk decision，不重写 pipeline。
- 修改 approval payload 创建逻辑：加入 `checkpoint_id`、`interrupt_payload`。
- 新增 `tests/test_graph_interrupt_approval_v23.py`。

验收标准：

- high-risk tool 不被调用。
- 创建 approval 和 pending checkpoint。
- approval payload 可追溯到 checkpoint。
- `PolicyEngine` 风险语义不变。

风险：

- 同时存在 legacy approval 和 graph approval 两套 payload。
- 后续高风险 step 的新 approval 与旧 checkpoint 消费关系复杂。

### Phase 2.4：resume idempotency + restart recovery

修改/新增文件：

- 新增 `app/agent/graph/resume_adapter.py`。
- 修改 `app/services/approval_resume.py`：有 `checkpoint_id` 时委托 graph resume。
- 修改 `app/api/approvals.py`：保持响应兼容，透传 graph resume 结果。
- 可新增 `GET /tasks/{task_id}/graph-state` 到 `app/api/tasks.py`。
- 新增 `tests/test_graph_resume_v24.py`。

验收标准：

- approve -> graph resume -> task completed。
- reject -> checkpoint cancelled -> task cancelled。
- repeated resume 不重复执行工具。
- runtime reset 后仍可从 checkpoint 恢复。
- legacy resume 测试继续通过。

风险：

- resume 过程中工具成功但 checkpoint 更新失败。
- claim/consume 原子性不足导致重复执行。
- API 响应新增字段影响过窄断言测试。

### Phase 2.5：docs / metrics / release cleanup

修改/新增文件：

- 更新 `README.md`、`AGENTS.md`、`docs/enterprise_pilot_plan_v2.md`。
- 新增 release review 文档。
- 增加 metrics 字段或事件：checkpoint_created、graph_interrupted、graph_resumed、graph_resume_duplicate、checkpoint_expired。
- 补充 `RELEASE_NOTES.md`。

验收标准：

- 文档明确 Phase 2 已完成范围和非目标。
- 全量 pytest 通过。
- docker compose config 通过。
- 如新增 migration，docker compose build / startup migration 验证通过。

风险：

- 文档宣称超过实际实现范围。
- metrics 口径与旧 runtime metrics 混淆。

## 8. 风险与非目标

### 8.1 主要风险

- 把当前确定性 Harness 编排误改成“完全自治多 Agent”，导致项目定位偏移。
- graph runtime 与 legacy runtime 双路径长期不一致。
- checkpoint state 过大或包含不可序列化对象。
- resume 幂等不是数据库原子操作，导致高风险工具重复执行。
- 审批、checkpoint、task 状态三者不一致。
- PostgreSQL 通过企业配置启用后与 SQLite fallback 行为不一致。

### 8.2 Phase 2 非目标

- 不在 Phase 2 接真实 MCP stdio。
- 不在 Phase 2 接真实 LLM。
- 不在 Phase 2 接真实 LLM-as-Judge。
- 不在 Phase 2 做 Next.js 前端审批 UI。
- 不把确定性多角色编排包装成自治多 Agent。
- 不破坏 SQLite 默认兼容。
- 不默认开启 auth/rbac/redis/postgres。
- 不删除 v2.0.1 legacy approval/resume 路径。

## 9. Phase 2.1 进入条件

可以进入 Phase 2.1 的条件：

- 本规划文档评审通过。
- 明确 `graph_runtime_enabled` 默认关闭。
- 先实现 checkpoint store 和 schema 测试，再接 AgentKernel。
- 每个阶段都保持 legacy HITL 和 `/tasks` 成功流程回归通过。

# Interview Guide — Harness-native 运营中台 Agent

## 一句话

Harness-native 运营中台 Agent：可审批、可审计、可评测的 Agent Runtime 工程化项目。

## 2 分钟讲解稿

### 为什么先做 Harness Runtime，而不是先堆多 Agent

多数人拿到 Agent 项目第一反应是"接 LLM、做多 Agent 协作"。但生产环境的核心问题不是"Agent 能不能对话"，而是"Agent 行为是否可控、可审计、可回滚"。所以本项目先做 Harness Runtime——一个五层管线驱动的执行框架，所有 Agent 行为（规划、执行、校验、审批、审计）都通过管线驱动，而不是裸调用 LLM。

### Harness 五层

1. **ContextAssembler**：注入可用工具列表、策略配置、追踪上下文
2. **ToolGateway**：统一工具注册/发现/调用，支持 local callable 与 MCP Client 双通道
3. **HookPipeline**：可插拔 Hook 管线，pre_execute / post_execute / on_error 三阶段
4. **PolicyEngine**：风险分级策略引擎，low 放行、medium 放行、high 触发审批
5. **TraceRecorder**：执行链路追踪，每步事件记录，支持 timeline 回放

### NL2SQL

从自然语言到安全 SQL 执行的完整评测管线：Schema 提取 → 剪枝 → 生成 → SQLGuard（只允许 SELECT）→ 只读执行 → 格式化 → 图表规格。支持 MockNL2SQLGenerator（零依赖）和 LLMNL2SQLGenerator（可插拔 Provider）。

### Tool Gateway

统一管理本地工具（5 个 ops_query）和 MCP 远程工具（FakeMCPClient 提供 date_lookup / calculator / rule_lookup）。StdioMCPClient 是真实 MCP stdio 协议占位，通过 MCP_MODE=real 环境变量切换。

### HITL

高风险操作触发人工审批：PolicyEngine 判定 high risk → 任务进入 waiting_approval → 审批通过后恢复执行（幂等，approval_consumed 语义）→ 审批拒绝后任务取消。MultiTool Pipeline 支持审批通过后继续执行后续步骤。

### Trace / Audit / Metrics

- TraceRecorder：任务级执行链路追踪，细粒度每步记录
- AuditRecorder：append-only 合规审计日志，不可变、不可删除
- RuntimeMetricsRecorder：运行时指标采集（任务数 / 工具调用数 / 延迟），内存 + SQLite 双写

### Trajectory Eval

TrajectoryEvaluator 从 trace_events 中校验执行轨迹：expected_mode / expected_roles / expected_tools / expected_events / approval_required / max_steps。任何显式 expectation 缺失标记 `critical:`，passed 需要 score >= 0.8 且无 critical issues。支持递归提取工具名（extract_tool_names），从嵌套的 tool_calls 结构中提取。

## 高频追问

### 为什么不是完全自治多 Agent？

当前 Multi-Agent 是确定性多角色编排（deterministic multi-role orchestration），Coordinator / Analyst / Executor / Reviewer 四个角色的边界划分由规则驱动。这样做的优势：行为可预测、可测试、可审计。完全自治多 Agent 需要 LLM 自主决策，引入不确定性，当前作为 Roadmap 保留。

### LangGraph 在项目里到底实现到什么程度？

v1.1 引入了最小 StateGraph 骨架：AgentKernel.build_graph() 实现了 assemble_context → plan → execute → verify → respond 的有向图，get_graph_summary() 返回节点和边。但完整 checkpoint 持久化、interrupt/resume 机制仍在 Roadmap。当前主链路仍以 Harness Runtime 顺序流为主。

### MCP 是真实接入了吗？

当前使用 FakeMCPClient，内置 3 个 MCP 工具（date_lookup / calculator / rule_lookup），零外部依赖。StdioMCPClient 是真实 MCP stdio 协议的占位实现，通过 MCP_MODE=real 环境变量切换，但需要真实 MCP Server 配合。真实 MCP stdio 接入在 Roadmap 中。

### HITL resume 如何保证幂等？

approval_consumed 语义：审批通过后执行被拦截的 step，执行成功后原 approval 标记为已消费。重复 resume 不会重复调用工具。MultiTool Pipeline 的 resume 不仅执行被拦截 step，还继续执行后续 steps。

### Prompt Injection 怎么防？

三层安全防线：
1. PromptInjectionGuard：规则型三级检测（high → block bypass approval / DROP TABLE；medium → block reveal prompt / ignore instructions；low → warn 模糊注入）
2. OperationWhitelist：keyword 允许 read 工具、nl2sql 只允许 SELECT、multitool 只允许注册工具
3. PolicyEngine：风险分级 + 审批触发

检测覆盖：query 注入、工具参数注入、approval reason 注入、resume payload 篡改。

### Eval 如何避免虚假通过？

- TrajectoryEvaluator passed 判定收紧：score >= 0.8 且无 critical issues
- 无 trace_recorder 时 trajectory 记为失败，不虚假通过
- extract_tool_names 递归提取，不遗漏嵌套工具调用
- expected_tools 按真实 trace 校准，不硬填
- MultiAgentEvalRunner 不经过 /tasks API 的 PromptInjectionGuard，security case 只验证 outcome（注入查询不会成功执行），不验证 injection_blocked 事件

### 为什么说是 production-grade prototype，不是 production-ready system？

- 真实 MCP stdio 未接入（使用 FakeMCPClient）
- 真实 LLM-as-Judge 未接入（使用 FakeJudge）
- LangGraph checkpoint / interrupt 未完整实现
- 前端审批 UI 未实现
- Multi-Agent 是规则驱动，非 LLM 自主决策
- 但 Runtime 治理、工具控制、审计追踪、HITL、评测闭环的工程化设计是生产级的

## 禁止夸大的表述

以下表述在面试和文档中**禁止使用**：

- ~~完全自治多 Agent~~ → 确定性多角色编排 / deterministic multi-role orchestration
- ~~已接真实 MCP stdio~~ → FakeMCPClient + StdioMCPClient 占位
- ~~已接真实 LLM-as-Judge~~ → FakeJudge + LLMJudgeProvider 占位
- ~~已完整实现 LangGraph checkpoint / interrupt~~ → 最小 StateGraph 骨架，完整 checkpoint / interrupt 在 Roadmap
- ~~可直接生产上线~~ → production-grade engineering prototype，不可直接用于生产环境

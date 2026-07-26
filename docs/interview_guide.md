# Interview Guide — Harness-native 运营中台 Agent

> 当前以 v5.0 面试主材料为准：`docs/resume_interview_optimization_pack_v50.md`。
> 真实业务系统暂未接入，当前展示 demo read-only 受控试点路径；`public_production_direct_launch=No-Go`。
> 不宣称公网生产可直接上线，不宣称真实业务系统生产验收完成。

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

从自然语言到安全 SQL 执行的完整评测管线：Schema 提取 → 剪枝 → 生成 → SQLGuard（只允许 SELECT）→ 只读执行（SQLite `mode=ro` 只读连接）→ 格式化 → 图表规格。支持 MockNL2SQLGenerator（零依赖）和 LLMNL2SQLGenerator（可插拔 Provider：fake 默认 / litellm 可选 / openai_compatible httpx 直连）。另有 SSE 流式端点 `/nl2sql/stream`（`NL2SQL_STREAM_ENABLED` 默认开启），逐 chunk 下发 stage / sql_delta / guard / execution / done 事件，完整复用注入检查、SQLGuard、只读执行与审计链路。

### Tool Gateway

统一管理本地工具（ops_query 系列）和 MCP 远程工具（FakeMCPClient 提供 date_lookup / calculator / rule_lookup）。StdioMCPClient 已对齐 MCP 2024-11-05 协议：initialize 握手携带 protocolVersion/capabilities/clientInfo 并校验 server 返回版本、握手后补发 `notifications/initialized`、`tools/call` 的 `isError=true` 映射为失败结果；默认 `MCP_MODE=fake`，通过 `MCP_MODE=real` + command/allowlist 显式切换。

### HITL

高风险操作触发人工审批：PolicyEngine 判定 high risk → 任务进入 waiting_approval → 审批通过后恢复执行（幂等，approval_consumed 语义）→ 审批拒绝后任务取消。MultiTool Pipeline 支持审批通过后继续执行后续步骤。默认注册高风险演示工具 `simulate_refund_order`（纯内存仿真写操作，`DEMO_HIGH_RISK_TOOL_ENABLED` 控制），"为订单 XX 模拟退款"可现场走完 waiting_approval → 审批 → resume 全链路。

### Trace / Audit / Metrics

- TraceRecorder：任务级执行链路追踪，细粒度每步记录
- AuditRecorder：append-only 合规审计日志，不可变、不可删除
- RuntimeMetricsRecorder：运行时指标采集（任务数 / 工具调用数 / 延迟），内存 + SQLite 双写

### Trajectory Eval

TrajectoryEvaluator 从 trace_events 中校验执行轨迹：expected_mode / expected_roles / expected_tools / expected_events / approval_required / max_steps。任何显式 expectation 缺失标记 `critical:`，passed 需要 score >= 0.8 且无 critical issues。支持递归提取工具名（extract_tool_names），从嵌套的 tool_calls 结构中提取。

## 高频追问

### 为什么不是完全自治多 Agent？

当前 Multi-Agent 是确定性多角色编排（deterministic multi-role orchestration），Coordinator / Analyst / Executor / Reviewer 四个角色的边界划分由规则驱动。这样做的优势：行为可预测、可测试、可审计。Coordinator 提供可选的 LLM 路由决策（`COORDINATOR_LLM_ENABLED`，默认关闭，且与关键词规则交叉验证置信度），但角色协作本身仍是规则编排，不是 LLM 自主协作，完全自治多 Agent 作为 Roadmap 保留。

### LangGraph 在项目里到底实现到什么程度？

keyword 主链路已经过真实的 LangGraph StateGraph 执行：AgentKernel.build_graph() 把 assemble_context → plan → execute → verify → respond 五个节点编译为图（各节点包装既有私有方法），execute 后有条件边——任务进入 waiting_approval 时跳过 verify 直达 respond；run() 首次调用时懒构建图并经 graph.invoke 执行，langgraph 不可用时降级为行为等价的顺序执行，trace 的 task_started 事件以 engine=langgraph|sequential 注明实际引擎。nl2sql / multitool / multi_agent 模式仍为管道式执行；checkpoint 持久化与 HITL 恢复由自研 GraphRuntimeAdapter 状态机负责（默认 graph_runtime_enabled=false），未使用 LangGraph 原生 checkpointer / Command resume。

### LangGraph 图具体如何执行？条件边解决什么问题？

图节点只做"包装"不复制业务逻辑，策略评估、审批创建、trace/metrics/memory 时序全部保留在既有私有方法内，图执行与顺序执行的 trace 事件序列有测试断言完全等价。条件边解决高风险拦截：execute 节点把 task.status==waiting_approval 写入图状态，条件边据此跳过 verify，避免对未执行的工具做校验、也避免记 task_completed。

### 为什么自研 checkpoint 状态机而不是 LangGraph 原生 checkpointer？

审批恢复需要与 ApprovalStore、审计链路和任务状态机（waiting_approval → resume / cancel）深度耦合：审批单 payload 要持久化完整调用上下文、resume 要保证幂等（approval_consumed）、拒绝要级联取消任务并留审计证据。自研 GraphCheckpointStore + GraphRuntimeAdapter 能直接复用这套治理语义；LangGraph 原生 checkpointer / Command resume 的接入成本与收益不匹配，作为 Roadmap 保留，文档与代码 docstring 均如实注明。

### PLANNER_MODE=llm 的 function calling 降级链是怎样的？

LLMToolPlanner 把 ToolGateway 注册的 ToolSpec 转为 OpenAI function calling tools（parameters 取 input_schema），调 provider.generate_with_metadata(tools=...) 后解析首个 tool_call。五个失败触发点全部降级 KeywordPlanner 并以前缀化 fallback_reason 写入 plan_result：no_tools_available / provider_error / no_tool_call / unknown_tool / invalid_arguments。参数经手写最小 JSON Schema 校验：未声明参数丢弃（防参数注入）、类型不符或缺 required 才整体拒绝。默认 planner_mode=keyword 行为不变；fake provider 下 LLM planner 可离线演示。治理层不动：高风险工具经 LLM planner 选中仍走 PolicyEngine → 审批链路。

### MCP 是真实接入了吗？

当前默认使用 FakeMCPClient，内置 3 个 MCP 工具（date_lookup / calculator / rule_lookup），零外部依赖。StdioMCPClient 已对齐 MCP 2024-11-05 协议（initialize 三要素握手 + 版本协商校验 + notifications/initialized + isError 映射），并可在 `MCP_MODE=real` 下配合 fake stdio fixture 验收；真实外部 MCP Server 生产验收仍在后续阶段。

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

- 真实 MCP stdio protocol path 已接入（对齐 MCP 2024-11-05），但默认仍使用 FakeMCPClient（`MCP_MODE=fake`），真实外部 MCP Server 生产验收未完成
- LLM provider 层支持 function calling / 流式 / OpenAI 兼容直连，但默认仍 fake/offline；真实 LLM 仅有 opt-in 试点工具链（`scripts/run_llm_pilot.py`），生产验收仍需外部环境和密钥单独完成
- keyword 主链路已经过 LangGraph 图执行，但 checkpoint / HITL 恢复是自研状态机（默认关闭的 GraphRuntimeAdapter 路径），未接入 LangGraph 原生 checkpointer / Command resume
- 前端为试点级运营台（可离线构建的 Next.js 多页面控制台），不宣称生产级前端交付完成
- Multi-Agent 角色协作是规则驱动；LLM 路由决策与 LLM 工具规划均为默认关闭的 opt-in 能力
- 但 Runtime 治理、工具控制、审计追踪、HITL、评测闭环的工程化设计是生产级的

## 禁止夸大的表述

以下表述在面试和文档中**禁止使用**：

- ~~完全自治多 Agent~~ → 确定性多角色编排 / deterministic multi-role orchestration（LLM 路由决策为默认关闭的可选项）
- ~~已完成真实外部 MCP Server 生产验收~~ → 当前完成 MCP 2024-11-05 协议对齐 + fake stdio fixture 验收
- ~~已接真实 LLM-as-Judge~~ → 当前为 FakeJudge 默认路径，LLMJudgeProvider 提供可选真实 provider 路径（默认不启用）
- ~~已完整实现 LangGraph checkpoint / interrupt~~ → keyword 主链路经 LangGraph StateGraph 真实执行（含条件边），checkpoint / HITL 恢复为自研 GraphRuntimeAdapter 状态机，LangGraph 原生 checkpointer / Command resume 在 Roadmap
- ~~LLM 自主规划已默认启用~~ → planner_mode 默认 keyword；LLM function calling 规划为 opt-in（PLANNER_MODE=llm），失败降级关键词规则
- ~~已完成真实 LLM 生产验收~~ → 仅有 opt-in 试点工具链与 runbook，未配置真实 provider 时拒绝生成报告
- ~~可直接生产上线~~ → production-grade engineering prototype，不可直接用于生产环境

# Project B: Harness-native 运营中台 Agent — 简历与博客素材 v1.0

---

## 一、简历项目描述

### 简短版（2-3 句话）

设计并实现 Harness-native 运营中台 Agent 系统，以五层 Harness Runtime 为底座，集成 Tool Gateway、HITL 审批链路、Prompt Injection 防御和可观测性体系，支持 keyword / NL2SQL / multitool / multi_agent 四种执行模式。生产级工程化框架，包含 30+ BadCase 回归集、append-only 审计和 Cost Dashboard API。

### 技术版（5-6 句话）

基于 Python + FastAPI + LangGraph 构建 Harness-native 运营中台 Agent，核心架构为五层 Harness Runtime（ContextAssembler → HookPipeline → PolicyEngine → TraceRecorder → AuditRecorder）。Tool Gateway 统一管理 local 工具和 MCP 远程工具的注册/调用，支持 retry_policy 重试策略。HITL 审批链路实现七层生产策略（InjectionGuard → Whitelist → Policy → Approval → Resume → Trace → Audit），通过 approval_consumed + resumed 标记 + payload 完整性校验保证幂等。安全层采用三级规则检测（high/medium-block/medium-warn）+ payload 递归扫描防御 Prompt Injection。Eval 体系包含 30+ BadCase 回归集和 FakeJudge / LLMJudgeProvider 双骨架。可观测性通过 RuntimeMetricsRecorder 双写内存+SQLite，提供 Cost Dashboard API 支持 by_mode / by_day 维度查询。

### 面试讲解版（8-10 句话）

这个项目的核心思路是"先做 Harness 再调 LLM"——大多数 Agent Demo 直接把 LLM 当核心，但生产环境需要的是稳定的执行框架。我设计了五层 Harness Runtime：ContextAssembler 组装上下文、HookPipeline 提供扩展点、PolicyEngine 做策略决策、TraceRecorder 记录追踪、AuditRecorder 写审计日志，每一层都可以独立测试和替换。工具调用统一走 Tool Gateway，local 工具和 MCP 远程工具用同一套接口注册和调用，内置 retry_policy。HITL 不是可选功能而是必须——高风险操作必须经过人工审批，resume 时通过 approval_consumed 标记 + payload 完整性校验保证幂等，防止审批后被篡改。安全方面做了三级 Prompt Injection 检测，high 级直接 block，medium 级分 block 和 warn，payload 层面做递归扫描。Eval 用 30+ BadCase 做回归，直接调 InjectionGuard.check_text 和 SQLGuard.check，不走 LLM 判断，避免"LLM 评 LLM"的虚假通过。成本统计用 RuntimeMetricsRecorder 双写内存和 SQLite，Cost Dashboard API 支持 by_mode 和 by_day 两个维度。整个系统的设计决策是：宁可多一层抽象，也不要在生产环境裸调 LLM。

---

## 二、技术亮点

### 1. Harness Runtime 五层架构：为什么不是直接调 LLM，而是先做 Runtime

- 直接调 LLM 的问题是：没有上下文组装、没有策略拦截、没有追踪审计，出了问题无法定位
- 五层 Runtime（ContextAssembler → HookPipeline → PolicyEngine → TraceRecorder → AuditRecorder）每一层职责单一、可独立测试
- AgentKernel 作为编排入口，按 assemble_context → plan → execute → verify → respond 流程串联五层
- 这种设计让后续加 NL2SQL / multitool / multi_agent 模式时，只需扩展 execute 层，不需要改框架

### 2. 可恢复任务流：HITL approval + resume + approval_consumed 幂等

- 高风险工具被 PolicyEngine 拦截后，自动创建 approval 记录，任务进入 waiting_approval 状态
- 人工审批通过后，ApprovalResumeService.resume() 恢复执行，支持 keyword 和 multitool 两种 resume 模式
- 幂等保证：payload.resumed 标记防止重复执行，approval_consumed 标记防止重复消费，payload 完整性校验（check_payload_integrity）防止审批后被篡改
- multitool resume 支持 $variable 引用前序步骤结果（_resolve_arguments），以及下游步骤依赖检查（depends_on）

### 3. Tool Gateway：local + MCP 统一注册/调用，retry_policy

- ToolGateway 统一管理本地工具（register + callable）和 MCP 远程工具（register_mcp_server + discover_mcp_tools）
- 调用入口统一为 gateway.call(tool_name, arguments)，内部根据 spec.source 分发到 _call_local 或 _call_mcp
- retry_policy 在 ToolSpec 中配置 max_retries，失败后自动重试，重试次数记录在 ToolCallRecord.retry_count
- 所有调用结果封装为 ToolCallRecord（call_id / status / latency_ms / retry_count），统一异常处理，不抛未处理异常

### 4. HITL 审批链路：七层生产策略（InjectionGuard → Whitelist → Policy → Approval → Resume → Trace → Audit）

- 第一层 InjectionGuard：三级规则检测（high-block / medium-block / medium-warn），payload 递归扫描
- 第二层 OperationWhitelist：工具必须在 ToolGateway 注册，nl2sql 模式禁止 write/admin/schema 权限
- 第三层 PolicyEngine：高风险工具自动拦截，返回 requires_approval 决策
- 第四层 Approval：创建审批记录，任务进入 waiting_approval 状态，等待人工决策
- 第五层 Resume：审批通过后恢复执行，payload 完整性校验防止篡改，approval_consumed 保证幂等
- 第六层 Trace：TraceRecorder 记录 approval_resume_started / approval_payload_tampered / approval_resume_completed 等事件
- 第七层 Audit：AuditRecorder append-only 写入审计日志，记录 actor / action / outcome / severity

### 5. Eval / BadCase：30+ bad case 回归集，FakeJudge + LLMJudgeProvider 骨架

- 30+ BadCase 覆盖 6 个 suite：security（8 cases）、nl2sql（6 cases）、multitool（5 cases）、approval（5 cases）、multi_agent（4 cases）、runtime（2 cases）
- BadCaseRunner 直接调 InjectionGuard.check_text 和 SQLGuard.check，不走 LLM 判断，避免"LLM 评 LLM"的虚假通过
- FakeJudge 实现精确匹配 + rubric 匹配 + blocked-like 模糊匹配，用于 CI 快速回归
- LLMJudgeProvider 骨架已就位，配置 LITELLM_API_KEY 后可切换为 LLM 评判，实现渐进式质量提升

### 6. Audit / Metrics：append-only 审计 + SQLite 持久化 + Cost Dashboard API

- AuditRecorder 通过 SQLiteAuditStore append-only 写入，记录 event_type / actor / task_id / approval_id / action / outcome / severity
- RuntimeMetricsRecorder 双写：内存计数器（task_count / tool_call_count / total_cost）+ SQLite 三表（runtime_task_metrics / runtime_tool_metrics / runtime_token_usage）
- SQLiteMetricsStore 提供 summary / task_summary / tool_summary / cost_summary 四个 API
- Cost Dashboard API 支持 by_mode（按执行模式）和 by_day（按日期）两个维度查询 token 用量和成本

---

## 三、面试问答

### Q1：为什么不是一开始多 Agent？→ 先做 Harness Runtime 稳定底座，再逐步加 Agent 能力

多 Agent 是能力层，不是基础层。如果一开始就做多 Agent，每个 Agent 都要自己处理上下文组装、策略拦截、追踪审计，代码会大量重复且难以维护。我的做法是先做 Harness Runtime 五层架构（ContextAssembler / HookPipeline / PolicyEngine / TraceRecorder / AuditRecorder），确保单 Agent 链路稳定，然后通过 AgentKernel 的 mode 参数逐步扩展：v0.1 keyword 单工具 → v0.2 NL2SQL → v0.3 multitool 多工具串联 → v0.3+ multi_agent 多 Agent 协作。每一层复用同一个 Harness，新增模式只需扩展 execute 逻辑。这样 MultiAgentOrchestrator 里的 Coordinator / Analyst / Executor / Reviewer 都走同一个 ToolGateway 和 PolicyEngine，不需要每个 Agent 自己实现安全策略。

### Q2：Harness 和 LangGraph 怎么分工？→ Harness 管执行框架（上下文/策略/追踪），LangGraph 管图编排

Harness 是"执行框架"，负责 Agent 运行时需要的所有横切关注点：上下文怎么组装、策略怎么判断、追踪怎么记录、审计怎么写入。LangGraph 是"图编排"，负责定义 Agent 的执行流程——哪些节点、怎么连线、条件分支怎么走。在当前实现中，AgentKernel 预留了 build_graph() 方法对接 LangGraph，但核心执行逻辑（assemble_context → plan → execute → verify → respond）已经是图节点的形态。分工的好处是：换图编排框架不需要改 Harness 层，换 Harness 组件不需要改图定义。实际上面试时可以说：Harness 是"管子"，LangGraph 是"管子怎么连"。

### Q3：如何防 Prompt Injection？→ 三级规则检测 + payload 递归扫描 + 白名单 + 策略引擎

PromptInjectionGuard 实现三级检测：high-block 级（绕过审批/删除表/自动批准等 14 条规则）直接拦截返回 action=block；medium-block 级（泄露系统提示词/忽略指令等 7 条规则）也直接拦截；medium-warn 级（模糊注入模式 3 条规则）返回 action=warn。检测不仅针对文本，还通过 check_payload 对 payload 做递归扫描——_collect_strings 遍历 dict/list/tuple 中所有字符串字段逐一检测。在 InjectionGuard 之外还有 OperationWhitelist（工具必须注册才能调用）和 PolicyEngine（高风险工具需要审批），三层防御确保即使 LLM 被诱导，也无法执行未授权操作。

### Q4：HITL resume 怎么保证幂等？→ approval_consumed + resumed 标记 + payload 完整性校验

幂等保证分三个层面。第一层是 resumed 标记：resume() 入口检查 payload.resumed，如果已经 resume 过，直接返回 already_resumed=True 和上次的结果，不会重复执行工具。第二层是 approval_consumed 标记：工具调用成功后，结果中 approval_consumed=True，此时 update_payload 写入 resumed=True + approval_consumed=True，表示这个审批已经被消费；如果调用失败，approval_consumed=False，只记录 resume_attempt_count，允许重试。第三层是 payload 完整性校验：resume 前调用 OperationWhitelist.check_payload_integrity，检查 payload.tool_name 是否和审批记录一致、step_id 是否在原 plan.steps 中，防止审批通过后有人篡改 payload 换成危险工具。

### Q5：Eval 如何避免虚假通过？→ BadCase 回归集 + SQLGuard 直接调 check + approval 真实化

虚假通过的核心问题是"LLM 评 LLM"——用 LLM 做 Judge，它可能对同类输出宽容。我的做法是分层：security suite 直接调 PromptInjectionGuard.check_text，nl2sql suite 直接调 SQLGuard.check，不走 LLM。这些是确定性检测，输入相同输出一定相同，不会出现"这次通过下次不通过"的情况。approval suite 做真实化测试：创建真实 approval 记录 → 审批/拒绝/篡改 payload → 调 ApprovalResumeService.resume() → 检查返回的 error_type 是否和预期一致。FakeJudge 用于 CI 快速回归，只做精确匹配和 rubric 匹配；LLMJudgeProvider 骨架已就位，配置 API Key 后可切换为 LLM 评判，但这是补充不是替代。

### Q6：如何统计成本？→ RuntimeMetricsRecorder 双写内存+SQLite，Cost Dashboard API by_mode/by_day

RuntimeMetricsRecorder 在每次 record_task / record_tool_call / record_token_usage 时双写：内存计数器实时更新（task_count / total_cost 等），同时通过 SQLiteMetricsStore 写入 SQLite 三表（runtime_task_metrics / runtime_tool_metrics / runtime_token_usage）。内存计数器用于 summary() 快速返回，SQLite 用于持久化和时间范围查询。Cost Dashboard API 由 SQLiteMetricsStore.cost_summary() 提供，支持 start_time / end_time 时间范围过滤，返回 by_mode（按执行模式：keyword / nl2sql / multitool / multi_agent）和 by_day（按日期）两个维度的 prompt_tokens / completion_tokens / cost 聚合。by_mode 的实现是先从 runtime_task_metrics 构建 task_id→mode 映射，再关联 runtime_token_usage 计算。

---

## 四、博客大纲：从"多 Agent 调工具"到"生产级 Agent Harness"

### 引言：为什么大多数 Agent Demo 不能上生产

- Agent Demo 的典型路径：LLM + Function Calling + 几个工具 = Demo 完成
- 上生产遇到的问题：没有策略拦截（高风险操作直接执行）、没有审批链路（人不在回路）、没有注入防御（用户输入可以诱导 LLM 执行危险操作）、没有追踪审计（出了问题无法回溯）、没有成本统计（token 费用不可控）
- 核心论点：生产级 Agent 不是"调 LLM 调得好"，而是"框架稳得住"

### 第一层：Harness Runtime — 先做框架再调 LLM

- 为什么不是直接调 LLM：裸调 LLM 没有上下文组装、没有策略拦截、没有追踪审计
- 五层架构设计：ContextAssembler（组装上下文）→ HookPipeline（扩展点）→ PolicyEngine（策略决策）→ TraceRecorder（事件追踪）→ AuditRecorder（审计日志）
- AgentKernel 编排流程：assemble_context → plan → execute → verify → respond
- 设计决策：每一层职责单一、可独立测试、可替换，后续加模式只需扩展 execute 层

### 第二层：Tool Gateway — 统一工具调用入口

- 问题：local 工具和 MCP 远程工具调用方式不同，直接在 Agent 里写 if-else 分发
- ToolGateway 设计：register + register_mcp_server 统一注册，call(tool_name, arguments) 统一调用
- retry_policy：在 ToolSpec 中配置 max_retries，失败自动重试，retry_count 记录在 ToolCallRecord
- 统一异常处理：未注册工具、MCP 不存在、调用异常都返回 failed ToolCallRecord，不抛未处理异常

### 第三层：HITL — 人在回路不是可选是必须

- 为什么 HITL 是必须：运营中台的高风险操作（写操作/删数据/改配置）不能让 Agent 自主决定
- 审批流程：PolicyEngine 拦截 → 创建 approval 记录 → 任务 waiting_approval → 人工审批 → resume 恢复执行
- 幂等保证：resumed 标记防重复执行，approval_consumed 标记防重复消费，payload 完整性校验防篡改
- multitool resume：支持 $variable 引用前序步骤结果，depends_on 依赖检查，下游高风险步骤自动创建新 approval

### 第四层：Security Gate — 注入防御 + 操作白名单

- PromptInjectionGuard 三级检测：high-block（14 条规则直接拦截）、medium-block（7 条规则拦截）、medium-warn（3 条规则警告）
- payload 递归扫描：check_payload 遍历 dict/list/tuple 中所有字符串字段，防止注入藏在嵌套结构里
- OperationWhitelist：工具必须在 ToolGateway 注册，nl2sql 模式禁止 write/admin/schema 权限
- PolicyEngine：高风险工具自动拦截返回 requires_approval，和 InjectionGuard + Whitelist 形成三层防御

### 第五层：Observability — Trace / Audit / Metrics 三位一体

- TraceRecorder：记录 task_started / context_assembled / plan_created / tool_called / task_completed / task_failed 等事件，支持按 task_id 和 event_type 过滤
- AuditRecorder：append-only 写入 SQLiteAuditStore，记录 actor / action / outcome / severity，不可篡改
- RuntimeMetricsRecorder：双写内存计数器 + SQLite 三表，record_task / record_tool_call / record_token_usage
- Cost Dashboard API：cost_summary 支持 by_mode 和 by_day 两个维度，task_id→mode 映射关联 token 用量

### 第六层：Eval — BadCase 回归 + Judge 骨架

- 30+ BadCase 覆盖 6 个 suite：security / nl2sql / multitool / approval / multi_agent / runtime
- 关键设计：security 和 nl2sql suite 直接调 InjectionGuard.check_text 和 SQLGuard.check，不走 LLM 判断
- FakeJudge：精确匹配 + rubric 匹配 + blocked-like 模糊匹配，CI 快速回归
- LLMJudgeProvider 骨架：配置 LITELLM_API_KEY 后可切换，渐进式质量提升

### 结语：生产级 Agent = Harness + Agent + Eval

- Harness 是底座：上下文组装 / 策略拦截 / 追踪审计 / 成本统计，这些和具体 Agent 无关
- Agent 是能力：keyword / NL2SQL / multitool / multi_agent，复用同一个 Harness
- Eval 是保障：BadCase 回归防止回归，Judge 骨架支持渐进式质量提升
- 一句话总结：先做框架再调 LLM，先做单 Agent 再做多 Agent，先做确定性检测再做 LLM 评判

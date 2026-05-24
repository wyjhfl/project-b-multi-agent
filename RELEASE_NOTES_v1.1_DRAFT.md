## Project B v1.1.0 — Credibility & Eval Hardening

### 定位

v1.1 基于 v1.0 发布后的审查意见，做**可信度和评测体系加固**。不推翻 v1.0，不做大重构。

> 本项目是 production-grade Agent Harness 工程原型，重点展示 Runtime 治理、工具控制、审计追踪、HITL 和评测闭环。真实 MCP stdio、真实 LLM-as-Judge、前端审批 UI、完全自治的 LLM 多 Agent 规划属于后续扩展。

### 表述对齐

- README / RELEASE_NOTES 增加明确边界说明：本项目是 production-grade Agent Harness 工程原型
- Multi-Agent 表述从"四角色编排"改为"确定性多角色编排 / deterministic multi-role orchestration"
- LangGraph 表述明确：v1.0 以 Harness Runtime 可测试顺序流为主，v1.1 引入最小 StateGraph；完整 checkpoint / interrupt 仍在 Roadmap
- Roadmap 新增 Real LangGraph checkpoint / interrupt
- AGENTS.md 更新版本路线到 v1.1，增加 Known Pitfalls（5 条常见误解）

### TrajectoryEvaluator

新增 `app/harness/eval/trajectory.py`：

- `TrajectoryExpectation`：expected_mode / expected_roles / expected_tools / expected_events / approval_required / max_steps / allow_fallback
- `TrajectoryEvalResult`：passed / score / issues / matched_roles / matched_tools / matched_events
- `TrajectoryEvaluator.evaluate(trace_events, expectation)`：从 trace_events 提取信息，校验各类期望，输出 score
- `extract_tool_names(obj)`：递归提取工具名，支持 detail.tool_name / detail.tool_calls[] / 任意嵌套结构
- passed 判定收紧：任何显式 expectation 缺失标记 `critical:`，passed 需要 `score >= 0.8` 且无 critical issues

### Multi-Agent Eval 扩展

- `multi_agent_cases.json` 从 12 条扩展到 25 条
- 新增 category 字段：nl2sql(7) / multitool(6) / multi_agent(4) / hitl(4) / security(4)
- 每条新增 trajectory_expectation 字段
- expected_events 按真实 MultiAgentOrchestrator trace 校准（multi_agent_started / coordinator_decided / executor_completed / reviewer_completed 等）

### MultiAgentEvalRunner 增强

- 接入 TrajectoryEvaluator
- EvalFailure 新增：failure_stage / trace_task_id / trajectory_issues
- EvalStats 新增：trajectory_passed / trajectory_failed / trajectory_accuracy
- API 响应新增 trajectory 指标
- 修复 no trace_recorder 虚假通过：无 trace_recorder 时 trajectory 记为失败

### 最小 LangGraph StateGraph 骨架

- `AgentKernel.build_graph()` 实现最小 StateGraph
- 节点：assemble_context → plan → execute → verify → respond
- 新增 `get_graph_summary()` 返回 implemented / nodes / edges
- 不替换现有主链路，仅用于 graph introspection 和 keyword smoke test

### 评测文档

- 新增 `docs/eval_report_v1.md`：评测维度 / 指标表 / 失败归因 / Trace 复盘示例
- Prompt Injection 复盘示例修正：明确 MultiAgentEvalRunner 不经过 /tasks API 拦截

### 测试

- 新增 30 个测试（trajectory 16 + multi_agent 10 + langgraph 5 - 1 旧测试移除）
- 总计 **400 passed**
- 原有 370 个测试全部通过

### 版本

- app.version: 1.1.0
- pyproject.toml version: 1.1.0

### Roadmap

| 方向 | 说明 |
|------|------|
| 真实 MCP stdio | StdioMCPClient 接入真实 MCP Server stdio 协议 |
| Real LangGraph checkpoint / interrupt | 完整 checkpoint 持久化与 interrupt/resume 机制 |
| 真实 LLM-as-Judge | LLMJudgeProvider 接入真实 LLM API |
| 前端审批 UI | 基于 Approval UI API 构建审批交互界面 |
| LLM 自主多 Agent 规划 | 从确定性多角色编排升级为 LLM 自主决策 |

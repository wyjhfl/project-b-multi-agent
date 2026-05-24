# AGENTS.md — 仓库级规则

## 语言

- 所有文档和注释使用**简体中文**

## 安全

- **禁止提交任何密钥、Token、API Key** 到仓库
- 敏感配置通过 `.env` 文件管理，`.env` 已在 `.gitignore` 中排除
- 使用 `.env.example` 提供配置模板

## 版本路线

| 版本 | 里程碑 | 核心交付 |
|------|--------|---------|
| **v0.1** | Harness Core | Harness 五层管线 + AgentKernel 主链路 + KeywordPlanner + SQLite demo + 5 个本地工具 |
| **v0.2** | NL2SQL Eval Harness | SchemaMetadataExtractor / SchemaPruner / SQLGuard / MockNL2SQLGenerator / LLMNL2SQLGenerator / SQLiteReadOnlyExecutor / SQLResultFormatter / ChartPlanner + 可插拔 LLM Provider |
| **v0.3** | MCP Gateway + MultiTool + MultiAgent Role Orchestration | FakeMCPClient + StdioMCPClient / MultiToolPipeline / MultiAgentOrchestrator（确定性多角色编排）/ Task Persistence + Docker |
| **v0.4** | HITL + Security + Audit | ApprovalStore / ApprovalResumeService / PromptInjectionGuard / OperationWhitelist / AuditRecorder + SQLiteAuditStore |
| **v0.5** | Runtime Hardening | RuntimeMetricsRecorder + SQLiteMetricsStore / 30+ BadCase + FakeJudge / ShortTermMemory + SkillRegistry + SelfCheckEngine / Cost Dashboard API / Runtime Snapshot |
| **v1.0** | Release | 全部能力稳定交付，370 个测试，生产级工程化框架 |
| **v1.1** | Credibility & Eval Hardening | 表述对齐 / TrajectoryEvaluator / Multi-Agent eval 扩展 / 最小 LangGraph StateGraph 骨架 |

## Known Pitfalls

- **Multi-Agent 是规则型多角色编排**：Coordinator / Analyst / Executor / Reviewer 当前是规则驱动边界划分，不是完全自治多 Agent。不要在文档或代码中包装为"自治多 Agent"。
- **StdioMCPClient 是占位**：当前 `MCP_MODE=fake` 下使用 FakeMCPClient，StdioMCPClient 不实现真实 MCP stdio 协议。
- **LLMJudgeProvider 是 skeleton**：不调用真实 LLM，返回 unavailable 提示。不要在评测结果中暗示 LLM-as-Judge 已实接。
- **LangGraph StateGraph 只做最小主链路验证**：v1.1 引入最小 StateGraph 用于 keyword 主链路 smoke test，完整 checkpoint / interrupt 是 Roadmap。不要声称已实现 LangGraph checkpoint 或 interrupt。
- **不要在文档中夸大为"生产环境即插即用"**：本项目是 production-grade engineering prototype，不可直接用于生产部署。

## 开发规范

- 改动后运行最小测试：`python -m pytest`
- 保持模块间低耦合，通过接口通信
- 新增模块必须有对应的 `__init__.py`
- Pydantic 模型放在 `app/models/schemas.py`
- Harness 组件放在 `app/harness/` 对应子模块
- 所有新增能力必须有测试

## 不要做的事

- 不要接入真实 MCP Server
- 不要接入真实 LLM API
- 不要做前端审批 UI
- 不要重写 Harness Runtime
- 不要把规则型 Multi-Agent 包装成自治多 Agent

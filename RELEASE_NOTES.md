## Project B v1.0.0 — Harness-native 运营中台 Agent

### 项目定位

**Harness-native 运营中台 Agent** 是一个以 Harness Runtime 为核心执行框架的生产级 AI Agent 工程化系统。通过三层架构（Harness Runtime + LangGraph Agent Kernel + MCP Tool Gateway）实现从自然语言查询到安全执行的全链路闭环。

核心理念：**Harness-native** — 所有 Agent 行为（规划、执行、校验、审批、审计）均通过 Harness Runtime 的五层管线驱动，而非裸调用 LLM。

> ⚠️ **注意**：本项目是 production-grade engineering prototype，展示了生产级 Agent 工程化框架的设计与实现。真实 MCP stdio / 真实 LLM provider / 前端审批 UI 等尚未接入，不可直接用于生产环境。

### 核心能力摘要

| 能力 | 说明 |
|------|------|
| **Harness Runtime 五层管线** | ContextAssembler → ToolGateway → HookPipeline → PolicyEngine → TraceRecorder |
| **NL2SQL Eval Harness** | Schema 提取 → 剪枝 → 生成 → SQLGuard → 执行 → 格式化 → ChartSpec |
| **MCP Tool Gateway** | 统一 local + MCP 工具注册/调用，FakeMCPClient + StdioMCPClient |
| **MultiTool Pipeline** | 规则型多工具串联，$var 变量解析，depends_on，retry_policy |
| **Multi-Agent Orchestration** | Coordinator / Analyst / Executor / Reviewer 四角色编排 |
| **HITL Approval Runtime** | high risk → approval → approve/reject → resume/cancel，幂等 |
| **Security Gate** | PromptInjectionGuard 三级检测 + OperationWhitelist + PolicyEngine |
| **Audit / Trace / Metrics** | append-only AuditRecorder + TraceRecorder + RuntimeMetricsRecorder + SQLiteMetricsStore |
| **BadCase Eval / Judge** | 30+ BadCase 回归集，6 suite，FakeJudge + LLMJudgeProvider |
| **Short Memory / Skills / Reflection** | ShortTermMemory + SkillRegistry + SelfCheckEngine |

### 快速启动

```bash
pip install -e ".[dev]"
python scripts/init_demo_db.py
uvicorn app.main:app --reload
```

Docker:

```bash
docker compose up --build
```

### Demo 路径

📖 [docs/demo_script_v1.md](docs/demo_script_v1.md) — 10 步 8-10 分钟 Demo 流程

### API 文档路径

📖 [docs/api_v1.md](docs/api_v1.md) — 10 模块 33 端点完整 API 文档

📖 [docs/architecture_v1.md](docs/architecture_v1.md) — 4 张 Mermaid 架构图

### 测试结果

```
370 passed, 1 warning
```

覆盖全部模块：NL2SQL / MCP Gateway / MultiTool / Multi-Agent / HITL / Security / Audit / Metrics / BadCase Eval / Memory / Skills / Reflection

### 后续 Roadmap

| 方向 | 说明 |
|------|------|
| 真实 MCP stdio | StdioMCPClient 接入真实 MCP Server stdio 协议 |
| 真实 LLM provider eval | LiteLLMProvider 接入真实 LLM API |
| 前端审批 UI | 基于 Approval UI API 构建审批交互界面 |
| LLM-as-Judge 实接 | LLMJudgeProvider 接入真实 LLM |
| LLM 自主多 Agent | 从 rule-based 升级为 LLM 自主决策 |
| 长期记忆 / 向量库 | 从 ShortTermMemory 升级为持久化 + 向量检索 |
| 持久化 Skill Learning | 从规则型 SkillRegistry 升级为可学习技能系统 |
| Cost Dashboard 前端 | 基于成本 API 构建可视化看板 |
| 50+ BadCase | 扩展回归集到 50+ case |

# 架构设计文档

## 整体架构

Project B 采用 **Harness Runtime + LangGraph Agent Kernel + MCP Tool Gateway** 三层架构：

```
┌─────────────────────────────────────────────┐
│              Harness Runtime                │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │ Context  │ │  Policy  │ │   Trace    │  │
│  │Assembler │ │  Engine  │ │  Recorder  │  │
│  └──────────┘ └──────────┘ └────────────┘  │
│  ┌──────────┐ ┌──────────────────────────┐  │
│  │  Hook    │ │     Tool Gateway         │  │
│  │ Pipeline │ │  (Local + MCP)           │  │
│  └──────────┘ └──────────────────────────┘  │
├─────────────────────────────────────────────┤
│          LangGraph Agent Kernel             │
│  START → assemble_context → plan →         │
│  execute → verify → respond → END           │
├─────────────────────────────────────────────┤
│              Tools Layer                    │
│  ┌──────────┐ ┌──────────────────────────┐  │
│  │  Local   │ │     MCP Tools            │  │
│  │  Tools   │ │     (v0.3+)              │  │
│  │ (SQLite) │ │                          │  │
│  └──────────┘ └──────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## Harness Runtime

Harness Runtime 是整个系统的执行框架，负责：

- **ContextAssembler**: 上下文组装，将用户查询、历史对话、业务元数据组装为 AgentContext
- **ToolGateway**: 工具网关，统一管理本地工具和 MCP 远程工具的注册与调用
- **HookPipeline**: Hook 管线，在关键节点前后插入自定义钩子（异常不吞掉，记录 hook_errors）
- **PolicyEngine**: 策略引擎，校验动作是否被策略允许
- **TraceRecorder**: 追踪记录器，记录执行过程中的关键事件

## LangGraph Agent Kernel

Agent 内核基于 LangGraph 的 StateGraph 实现，图结构为：

```
START → assemble_context → plan → execute → verify → respond → END
```

- **assemble_context**: 调用 ContextAssembler 组装上下文
- **plan**: 调用 KeywordPlanner 进行关键词路由
- **execute**: 通过 ToolGateway 执行工具调用
- **verify**: 通过 PolicyEngine 校验执行结果
- **respond**: 生成最终响应

## v0.1 数据流

```
User Query → KeywordPlanner → ToolGateway → SQLite Tool → TraceRecorder → Response
```

1. 用户通过 `POST /tasks` 提交查询
2. KeywordPlanner 根据关键词匹配选择工具
3. ToolGateway 调用对应的 SQLite 查询工具
4. TraceRecorder 记录全链路事件
5. 返回结构化响应

## 版本规划

| 版本 | 目标 | 核心内容 |
|------|------|----------|
| v0.1 | Harness Core | Harness 五大组件 + AgentKernel 主链路 + SQLite 本地工具 + KeywordPlanner |
| v0.2 | NL2SQL Eval Harness | 自然语言转 SQL + 评估框架 + Harness Eval 集成 |
| v0.3 | Tool Gateway + Multi-Agent | MCP 远程工具接入 + 多 Agent 协作 |
| v0.4 | HITL Production Flow | Human-in-the-Loop 审批流 + 生产级策略 |
| v0.5 | Runtime Hardening | 运行时加固 + 可观测性 + 持久化 + 可视化看板 |

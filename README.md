# Project B: Harness-native 运营中台 Agent

> **Harness Runtime** + **LangGraph Agent Kernel** + **MCP Tool Gateway** — 生产级运营 Agent 工程化框架

> **⚠️ 边界说明（请务必阅读）**
>
> 本项目是 **production-grade Agent Harness engineering prototype**。当前 Multi-Agent 是 **deterministic multi-role orchestration**，不是完全自治多 Agent；当前已实现 real MCP stdio protocol path（基于 fake stdio fixture 验收），并提供 LiteLLMProvider/LLMJudgeProvider 可选真实 provider 路径（默认 fake/offline，默认测试不调用真实 LLM），但真实外部 MCP Server 与真实 LLM 生产验收仍需外部环境和密钥单独完成。当前已实现 graph checkpoint / interrupt / resume adapter 最小闭环，完整 LangGraph native checkpoint / Command interrupt / Command resume 仍在 Roadmap。

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue)](.github/workflows/ci.yml) [![Python](https://img.shields.io/badge/Python-3.11+-blue)](pyproject.toml) [![Tests](https://img.shields.io/badge/Tests-754%2B%20(4%20skipped)-passing-brightgreen)](tests/) [![Version](https://img.shields.io/badge/Release-v3.1.0--prep-yellow)]()

---

## 目录

- [项目定位](#项目定位)
- [架构总览](#架构总览)
- [核心能力](#核心能力)
- [快速启动](#快速启动)
- [核心 API 示例](#核心-api-示例)
- [测试](#测试)
- [版本路线](#版本路线)
- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [后续 Roadmap](#后续-roadmap)

---

## 项目定位

**Harness-native 运营中台 Agent** 是一个以 **Harness Runtime** 为核心执行框架的生产级 AI Agent 工程化系统。通过三层架构实现从自然语言查询到安全执行的全链路闭环：

| 层 | 组件 | 职责 |
|----|------|------|
| **执行框架层** | Harness Runtime | 上下文组装、策略引擎、Hook 管线、追踪记录、审计日志 |
| **Agent 内核层** | LangGraph Agent Kernel | 有向图编排：START → assemble_context → plan → execute → verify → respond → END |
| **工具网关层** | MCP Tool Gateway | 统一管理本地工具与 MCP 远程工具的注册、发现、调用 |

核心理念：**Harness-native** — 所有 Agent 行为（规划、执行、校验、审批、审计）均通过 Harness Runtime 的五层管线驱动，而非裸调用 LLM。

> **⚠️ 边界说明**
>
> 本项目是生产级 Agent Harness 工程原型，重点展示 Runtime 治理、工具控制、审计追踪、HITL 和评测闭环。当前已具备 real MCP stdio 协议链路（基于 fake stdio fixture 验收）和 LiteLLMProvider/LLMJudgeProvider 可选真实 provider 路径（默认 fake/offline）。v2.5.0 已完成“真实 LLM 可选验收包”，v2.6.0 已完成 Phase 6.0 Engineering Readiness（deployment guard、/deployment/check、生产模板与 prod 脚本），并保持 v2.4 试点级运营台闭环（Dashboard / Tasks / Approvals / Trace / Audit / Metrics / RBAC / Tools / NL2SQL + Docker 演示脚本）；默认 fake/offline，默认测试不调用真实 LLM；真实外部 MCP Server 与真实 LLM 生产验收仍需外部环境和密钥单独完成。
>
> - Multi-Agent 当前是**确定性多角色编排 / deterministic multi-role orchestration**（Coordinator / Analyst / Executor / Reviewer 规则驱动边界划分），后续可替换为 LLM Planner。
> - LangGraph 当前 v1.0 以 Harness Runtime 可测试顺序流为主，v1.1 引入最小 LangGraph StateGraph，用于 keyword 主链路验证；Phase 2 已实现 graph checkpoint / interrupt / resume adapter 最小闭环；完整 LangGraph native checkpoint / Command interrupt / Command resume 仍在 Roadmap。
> - 本项目不是生产环境即插即用系统，不可直接用于生产部署。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI API Layer                            │
│  /tasks  /nl2sql  /tools  /approvals  /audit  /metrics  /eval ... │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                    LangGraph Agent Kernel                           │
│  START → assemble_context → plan → execute → verify → respond → END│
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │Coordinator│ │ Analyst  │ │ Executor │ │ Reviewer │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                      Harness Runtime (五层)                         │
│  ContextAssembler → ToolGateway → HookPipeline → PolicyEngine →    │
│  TraceRecorder                                                      │
│                                                                     │
│  ┌───────────────┐ ┌──────────────┐ ┌────────────────────┐         │
│  │Security Gate  │ │HITL Approval │ │Audit / Metrics     │         │
│  │InjectionGuard │ │ApprovalStore │ │AuditRecorder       │         │
│  │OperationWhite │ │ResumeService │ │RuntimeMetrics      │         │
│  │PolicyEngine   │ │Idempotent    │ │SQLiteMetricsStore  │         │
│  └───────────────┘ └──────────────┘ └────────────────────┘         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                     MCP Tool Gateway                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Local Tools  │  │FakeMCPClient │  │StdioMCPClient│             │
│  │ ops_query ×5 │  │date_lookup   │  │stdio JSON-RPC│             │
│  │              │  │calculator    │  │              │             │
│  │              │  │rule_lookup   │  │              │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                      SQLite Storage Layer                           │
│  ops_demo.sqlite │ runtime.sqlite │ runtime_metrics.sqlite          │
└─────────────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────────────┐
│                   Auth / Cache / Storage Abstraction                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐     │
│  │ JWT Auth     │  │ RBAC         │  │ Store Factory        │     │
│  │ /auth/login  │  │ admin/operator│  │ sqlite / postgres    │     │
│  │ /auth/me     │  │ viewer/auditor│  │ InMemoryUserStore    │     │
│  └──────────────┘  └──────────────┘  └──────────────────────┘     │
│  ┌──────────────┐  ┌──────────────┐                               │
│  │ Redis Cache  │  │ PostgreSQL   │                               │
│  │ NoopRedis    │  │ Alembic      │                               │
│  └──────────────┘  └──────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 核心能力

### 1. Harness Runtime 五层管线

Harness Runtime 是整个系统的执行骨架，所有 Agent 行为均通过五层管线驱动：

| 层 | 组件 | 职责 |
|----|------|------|
| 1 | **ContextAssembler** | 组装 AgentContext：注入可用工具列表、策略配置、追踪上下文、用户信息 |
| 2 | **ToolGateway** | 统一工具注册/发现/调用，支持 local callable 与 MCP Client 双通道 |
| 3 | **HookPipeline** | 可插拔 Hook 管线：pre_execute / post_execute / on_error 三阶段，异常可观测 |
| 4 | **PolicyEngine** | 风险分级策略引擎：low 放行、medium 放行、high 触发审批流程 |
| 5 | **TraceRecorder** | 执行链路追踪：每步事件记录，支持 timeline 回放与事件查询 |

### 2. NL2SQL Eval Harness

从自然语言到安全 SQL 执行的完整评测管线，覆盖 schema 提取、剪枝、生成、守卫、执行、格式化、图表规划全链路：

| 组件 | 职责 |
|------|------|
| **SchemaMetadataExtractor** | 从 SQLite 自动提取表结构、字段类型、主键、示例值、行数统计 |
| **SchemaPruner** | 基于关键词规则的 schema 剪枝，缩小 LLM 生成时的 schema 上下文 |
| **SQLGuard** | SQL 安全守卫：只允许 SELECT / readonly CTE，拦截 DDL/DML/多语句/注释注入，自动追加 LIMIT |
| **MockNL2SQLGenerator** | 规则型 SQL 生成器，零依赖，无需 API Key 即可运行 |
| **LLMNL2SQLGenerator** | LLM 驱动的 SQL 生成器，支持 FakeLLMProvider / LiteLLMProvider，支持 fallback_to_mock |
| **SQLiteReadOnlyExecutor** | 只读 SQL 执行器：先过 SQLGuard，再执行 guard 后 SQL，最多 100 行，记录 latency_ms |
| **SQLResultFormatter** | 结果格式化：单行单指标 → 简短摘要，多行 → 行数说明，失败 → 原因说明 |
| **ChartPlanner** | 图表规格生成：metric / line / bar / table 四种类型，输出 JSON 规格，不依赖前端库 |

### 3. MCP Tool Gateway

统一管理本地工具与 MCP 远程工具的注册、发现、调用，实现工具层的抽象与可扩展：

- **统一注册**：`ToolSpec.source` 区分 `local` / `mcp`，调用方无需关心工具来源
- **FakeMCPClient**：内置 3 个 MCP 工具（date_lookup / calculator / rule_lookup），零外部依赖
- **StdioMCPClient**：真实 MCP stdio JSON-RPC 协议路径（subprocess + initialize + tools/list + tools/call）；默认仍 `MCP_MODE=fake`，real 模式需显式配置 command/allowlist
- **PolicyEngine 集成**：工具调用前自动过策略检查，high risk 触发审批

### 4. MultiTool Pipeline

规则型多工具串联编排，支持跨工具变量传递、依赖校验、重试策略：

- **规则型规划**：基于关键词匹配 intent，映射到预定义的多步骤工具链（GMV 环比 / 退款规则 / 促销规则）
- **`$var` 变量解析**：`$current_gmv.result.gmv` 引用前置步骤输出，支持嵌套 dict/list 路径解析
- **`depends_on` 校验**：每个步骤执行前检查依赖步骤是否已完成，缺失时返回 `missing_depends_on`
- **`retry_policy`**：`ToolSpec.retry_policy` 支持 `{"max_retries": 2}`，失败时同步重试，记录 `retry_count`

### 5. Multi-Agent Orchestration（确定性多角色编排）

四角色确定性编排（deterministic multi-role orchestration），实现查询路由 → 计划分析 → 工具执行 → 结果校验的完整决策链。当前角色边界划分由规则驱动，后续可替换为 LLM Planner：

| 角色 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **Coordinator** | 路由决策：选择 nl2sql / multitool / keyword / auto | query | selected_mode |
| **Analyst** | 计划解释：分析是否需要 schema / 多工具 | query + coordinator decision | plan_summary |
| **Executor** | 复用工具链执行 | selected_mode + query | execution_result |
| **Reviewer** | 结果校验 + fallback 建议 | execution_result | approved / suggested_fallback_mode |

执行链路：`Coordinator → Analyst → Executor → Reviewer`，Reviewer 不通过时一次 fallback，不无限循环。每个角色输出进入 `decisions` 列表，形成完整决策链。

### 6. HITL Approval Runtime

高风险操作的人工审批运行时，实现从拦截到审批到恢复执行的安全闭环：

- **high risk → approval**：PolicyEngine 判定 high risk 时，任务进入 `waiting_approval`，生成 ApprovalRequest
- **approve → resume**：审批通过后恢复执行（keyword / multitool），跳过 PolicyEngine（审批已通过）
- **reject → cancel**：审批拒绝后任务状态更新为 `cancelled`
- **幂等保证**：`approval_consumed` 语义，被审批 step 执行成功后原 approval 标记已消费，不重复调用工具
- **完整 MultiTool resume**：审批通过后不仅执行被拦截 step，还继续执行后续 steps，后续 high risk 创建新审批

### 7. Security Gate

三层安全防线，覆盖提示注入、操作白名单、策略引擎：

| 层 | 组件 | 职责 |
|----|------|------|
| 1 | **PromptInjectionGuard** | 规则型三级检测：high → block（bypass approval / DROP TABLE）、medium → block（reveal prompt / ignore instructions）、low → warn（模糊注入） |
| 2 | **OperationWhitelist** | 操作白名单：keyword 允许 read 工具、nl2sql 只允许 SELECT、multitool 只允许注册工具、resume payload 完整性校验 |
| 3 | **PolicyEngine** | 风险分级 + 审批触发：whitelist 通过 → risk 分级 → high risk 进入审批流程 |

检测覆盖：query 注入、工具参数注入、approval reason 注入、resume payload 篡改。

### 8. Audit / Trace / Metrics

全链路可观测体系，覆盖执行追踪、合规审计、运行时指标三大维度：

- **AuditRecorder**：append-only 合规审计日志，不可变、不可删除，写入 SQLiteAuditStore，覆盖安全事件 + 审批决策
- **TraceRecorder**：任务级执行链路追踪，细粒度（每步工具调用），支持 timeline 回放与事件查询
- **RuntimeMetricsRecorder**：运行时指标采集（任务数 / 工具调用数 / token 用量 / 成本 / 延迟），内存 + SQLite 双写
- **SQLiteMetricsStore**：三张 append-only 表（task_metrics / tool_metrics / token_usage），支持时间范围查询与汇总

### 9. BadCase Eval / Optional LLM-as-Judge

30+ BadCase 回归评测集 + LLM-as-Judge 评测骨架：

- **30+ BadCase**：覆盖 6 个 suite（security × 8 / nl2sql × 6 / multitool × 5 / approval × 5 / multi_agent × 4 / runtime × 2）
- **6 suite 分层**：security（注入绕过）、nl2sql（unmatched / dangerous SQL）、multitool（unknown tool / high risk）、approval（pending resume / payload tampered）、multi_agent（unknown / vague / mixed）、runtime（空状态）
- **FakeJudge**：规则型打分（expected==actual → 1.0，blocked-like → 0.8，mismatch → 0.0）
- **LLMJudgeProvider 可选实接**：支持通过可选真实 provider 路径进行评测（默认仍 FakeJudge/fake-offline，默认测试不调用真实 LLM）

### 10. Short Memory / Skills / Reflection

轻量认知增强层，提供短期记忆、技能注册、自检反思：

- **ShortTermMemory**：内存实现，`session_id` 共享，同一 session 下多次任务共享上下文，支持 add_message / get_messages / summarize / clear
- **SkillRegistry**：4 个内置 Skill（ops_metrics / product_analysis / policy_lookup / nl2sql_analysis），规则型 trigger 匹配
- **SelfCheckEngine**：8 项规则型自检（result_success / approval_consistency / injection_consistency / tool_call_consistency / nl2sql_consistency / audit_consistency / empty_result / waiting_approval），自检不改变 task.status

### 11. Auth / JWT / RBAC

企业级认证与授权层，默认 auth_enabled=false / rbac_enabled=false 保持兼容；v2.0.1 已把 require_permission 接入关键 API：

- **JWT 认证**：PyJWT 实现，POST /auth/login 获取 access_token，GET /auth/me 验证身份
- **密码安全**：bcrypt 哈希，hash_password() / verify_password()
- **RBAC 角色体系**：4 个角色（admin / operator / viewer / auditor），ROLE_HIERARCHY 继承，ENDPOINT_PERMISSIONS 细粒度控制
- **关键 API 保护**：/tasks 创建与读取、/approvals 读取/决策/resume、/audit/events、/tools/{tool_name}/call、/metrics/* 已接入 RBAC 依赖；/health 和 /auth/* 不加权限。
- **auth_enabled=false 兼容**：默认返回 DevUser(username="system", roles=["admin"])，旧 API 不需要 token
- **rbac_enabled=false 兼容**：认证打开但 RBAC 关闭时只校验 token，不做角色权限拦截。
- **InMemoryUserStore**：本地可测试用户存储，seed_default_admin_if_empty 通过 DEV_ADMIN_PASSWORD 环境变量设置默认密码

> **注意**：auth_enabled=false 是兼容默认值，不影响现有 API 和测试。企业试点时设置 AUTH_ENABLED=true 启用认证。

### 12. PostgreSQL / Redis / Store Abstraction

企业级存储与缓存层，默认 storage_backend=sqlite / redis_enabled=false 保持兼容：

- **Store Factory**：根据 storage_backend 配置返回 SQLite 或 PostgreSQL store 实现；v2.0.1 已接入 app.main 主链路 getter
- **PostgreSQL Store**：PostgresTaskStore / PostgresApprovalStore / PostgresAuditStore / PostgresMetricsStore，与 SQLite store 返回结构一致
- **Alembic 迁移**：7 张表（users / task_runs / approval_requests / audit_events / runtime_task_metrics / runtime_tool_metrics / runtime_token_usage）
- **Redis Cache**：NoopRedisClient（redis_enabled=false 时不连接），get_redis_client() / check_redis_health()
- **Docker Compose**：PostgreSQL 16-alpine + Redis 7-alpine + App 三容器编排；容器启动通过 scripts/start_app.py 先初始化 demo DB，PostgreSQL 模式下执行 alembic upgrade head，再启动 uvicorn

> **注意**：默认 storage_backend=sqlite，不要求 PostgreSQL/Redis 可用。企业试点时设置 STORAGE_BACKEND=postgres 且 DATABASE_URL 非空启用 PostgreSQL；REDIS_ENABLED=true 启用 Redis。

---

## 快速启动

### 本地启动

```bash
# 1. 安装依赖（含 dev）
pip install -e ".[dev]"

# 2. 初始化 demo 数据库（5 张运营表 + 模拟数据）
python scripts/init_demo_db.py

# 3. 启动服务
uvicorn app.main:app --reload
```

服务启动后访问 `http://localhost:8000/health` 验证。

### Docker 启动

```bash
docker compose up --build
```

### 健康检查

```bash
python scripts/check_health.py
```

检查端点：`/health` / `/tools` / `/eval/summary` / `/observability/tasks/summary`

---

## 核心 API 示例

### 任务创建（五种 mode）

```bash
# keyword 模式（默认，关键词路由 → ToolGateway）
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"query": "今天GMV多少"}'

# nl2sql 模式（NL2SQL Pipeline）
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"query": "今天GMV多少", "mode": "nl2sql"}'

# multitool 模式（多工具串联）
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"query": "GMV环比增长多少", "mode": "multitool"}'

# multi_agent 模式（四角色编排）
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"query": "退款规则是什么", "mode": "multi_agent"}'

# auto 模式（自动 fallback: NL2SQL → multitool → keyword）
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"query": "促销规则", "mode": "auto"}'
```

### NL2SQL 预览与执行

```bash
# 预览 SQL（只生成 + SQLGuard 校验，不执行）
curl -X POST http://localhost:8000/nl2sql/preview \
  -H "Content-Type: application/json" \
  -d '{"query": "今天GMV多少"}'

# 预览 SQL（LLM 生成器 + fake provider）
curl -X POST http://localhost:8000/nl2sql/preview \
  -H "Content-Type: application/json" \
  -d '{"query": "今天GMV多少", "generator": "llm", "provider": "fake"}'

# 执行 NL2SQL（生成 + 校验 + 安全执行 + 格式化 + 图表规格）
curl -X POST http://localhost:8000/nl2sql/execute \
  -H "Content-Type: application/json" \
  -d '{"query": "今天GMV多少"}'
```

### 工具管理

```bash
# 列出所有工具（local + mcp）
curl http://localhost:8000/tools

# 调用 MCP 工具
curl -X POST http://localhost:8000/tools/date_lookup/call \
  -H "Content-Type: application/json" \
  -d '{"arguments": {}}'

# 调用计算器
curl -X POST http://localhost:8000/tools/calculator/call \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"operation": "add", "a": 1, "b": 2}}'
```

### 审批管理

```bash
# 审批通过（默认自动恢复执行）
curl -X POST http://localhost:8000/approvals/{approval_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"decided_by": "admin", "reason": "允许执行"}'

# 审批拒绝（自动取消任务）
curl -X POST http://localhost:8000/approvals/{approval_id}/reject \
  -H "Content-Type: application/json" \
  -d '{"decided_by": "admin", "reason": "风险过高"}'
```

### 审计查询

```bash
# 查询审计事件（支持 event_type / task_id / outcome / severity 过滤）
curl http://localhost:8000/audit/events?event_type=prompt_injection_blocked

# 查询某任务的审计事件
curl http://localhost:8000/audit/events?task_id=task_xxx
```

### 运行时指标

```bash
# 内存指标汇总
curl http://localhost:8000/metrics/runtime

# 成本汇总（token 用量 + 成本 + by_mode + by_day）
curl http://localhost:8000/metrics/cost/summary

# 工具调用汇总（调用数 / 失败数 / 重试数 / 平均延迟 / by_tool）
curl http://localhost:8000/metrics/tools/summary

# 任务汇总（任务数 / 成功数 / 失败数 / 审批数 / 平均延迟 / by_mode）
curl http://localhost:8000/metrics/tasks/summary
```

### 运行时快照

```bash
# 运行时全量快照（版本 + metrics + cost + task + tool + audit + memory + skills）
curl http://localhost:8000/runtime/snapshot
```

### BadCase 评测

```bash
# 运行 BadCase 评测（支持 use_judge / limit / suite 参数）
curl -X POST http://localhost:8000/eval/bad-cases/run \
  -H "Content-Type: application/json" \
  -d '{"use_judge": true, "suite": "security"}'
```

### 记忆 / 技能 / 自检

```bash
# 查看短期记忆
curl http://localhost:8000/memory/{session_id}

# 匹配技能
curl -X POST http://localhost:8000/skills/match \
  -H "Content-Type: application/json" \
  -d '{"query": "今天GMV多少"}'

# 执行 Reflection 自检
curl -X POST http://localhost:8000/reflection/check \
  -H "Content-Type: application/json" \
  -d '{"task_id": "task_xxx", "result": {...}}'
```

### 认证与授权

```bash
# 登录获取 token（auth_enabled=true 时）
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# 查看当前用户信息
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <token>"
```

> **注意**：auth_enabled=false（默认）时，旧 API 不需要 token 仍可访问。

---

## 测试

```bash
python -m pytest -q
```

> 真实 LLM smoke 测试为 **opt-in**，默认不随 `python -m pytest -q` 执行。  
> 手动执行方式：`python -m pytest tests/test_real_llm_smoke_v52.py -m real_llm -q`  
> 需显式设置环境变量：`REAL_LLM_SMOKE_ENABLED=true`、`REAL_LLM_ACCEPTANCE_ENABLED=true`、`REAL_LLM_PREFLIGHT_ENABLED=true`、`REAL_LLM_PREFLIGHT_NETWORK_CHECK=true`。

当前基线：**754 passed, 4 skipped**，覆盖全部模块：

| 测试文件 | 覆盖范围 |
|---------|---------|
| test_project_bootstrap | 项目引导与基础结构 |
| test_nl2sql_v02 | NL2SQL 全链路（schema / pruner / guard / generator / executor / formatter） |
| test_mcp_gateway_v03 | MCP Tool Gateway（注册 / 发现 / 调用 / fake + stdio） |
| test_multitool_v03 | MultiTool Pipeline（变量解析 / depends_on / retry / policy） |
| test_multi_agent_v03 | Multi-Agent 编排（四角色 / fallback / eval） |
| test_v03_closure_mcp_docker | MCP + Docker 收口测试 |
| test_v036_persistence_eval | 持久化 + Eval 收口 |
| test_hitl_v04 | HITL 审批基础流程 |
| test_approval_resume_v042 | 审批恢复执行 |
| test_v043_full_resume | 完整 MultiTool Resume |
| test_security_v04 | 安全防线（注入 / 白名单 / 策略） |
| test_audit_v045 | 审计日志 |
| test_runtime_v05 | Runtime 加固 |
| test_runtime_hardening_v055 | Runtime 指标语义清理 |
| test_runtime_persistence_v05 | Metrics 持久化 |
| test_badcase_eval_v05 | BadCase 评测 |
| test_runtime_memory_skills_reflection_v05 | 记忆 / 技能 / 自检 |
| test_config_v20 | v2.0 配置与依赖基座 |
| test_auth_v20 | Auth / JWT / Password / UserStore |
| test_rbac_v20 | RBAC 角色权限 / API 保护开关 |
| test_storage_v20 | PostgreSQL Store / Alembic / Factory / Docker Compose |

---

## 版本路线

| 版本 | 里程碑 | 核心交付 |
|------|--------|---------|
| **v0.1** | Harness Runtime + KeywordPlanner | Harness 五层管线 + AgentKernel 主链路 + KeywordPlanner + SQLite demo + 5 个本地工具 |
| **v0.2** | NL2SQL Eval Harness + LLM Provider | SchemaMetadataExtractor / SchemaPruner / SQLGuard / MockNL2SQLGenerator / LLMNL2SQLGenerator / SQLiteReadOnlyExecutor / SQLResultFormatter / ChartPlanner + 可插拔 LLM Provider |
| **v0.3** | MCP Tool Gateway + MultiTool + MultiAgent | FakeMCPClient + StdioMCPClient / MultiToolPipeline（$var / depends_on / retry）/ MultiAgentOrchestrator（四角色）/ Task Persistence + Docker |
| **v0.4** | HITL Approval + Security Gate + Audit | ApprovalStore / ApprovalResumeService（幂等）/ PromptInjectionGuard / OperationWhitelist / AuditRecorder + SQLiteAuditStore |
| **v0.5** | Runtime Hardening + BadCase Eval + Memory/Skills/Reflection + Persistence + Cost Dashboard | RuntimeMetricsRecorder + SQLiteMetricsStore / 30+ BadCase + FakeJudge / ShortTermMemory + SkillRegistry + SelfCheckEngine / Cost Dashboard API / Runtime Snapshot |
| **v1.0** | 当前发布，完整工程化框架 | 全部能力稳定交付，370 个测试，生产级工程化框架 |
| **v1.1** | Credibility & Eval Hardening | 表述对齐（确定性多角色编排 / LangGraph 边界声明）/ TrajectoryEvaluator / Multi-Agent eval 扩展 / 最小 LangGraph StateGraph 骨架 / eval_report_v1.md |
| **v1.1.1** | Documentation & Eval Precision Cleanup | README/docs 口径统一 / expected_tools 补强 / HITL/Security eval semantic split / RiskIntentGuard / interview_guide / 432+ tests |
| **v2.0.1** | Phase 1 Foundation + Integration Cleanup | SQLAlchemy + Alembic + psycopg / Redis + NoopRedisClient / JWT Auth + bcrypt / RBAC 接入关键 API / Store Factory 接入 app.main / Docker startup migration / Dockerfile Alembic 修复 / tools:read / 553+ tests |
| **v2.1.0** | Graph Runtime Adapter | Phase 2.1 GraphCheckpointStore / Phase 2.2 GraphRuntimeAdapter feature flag / Phase 2.3 graph interrupt -> approval mapping / Phase 2.4 GraphResumeAdapter / Phase 2.5 release cleanup + failure-path hardening; default graph_runtime_enabled=false; legacy behavior unchanged; 553+ tests |
| **v2.2.0** | MCP Stdio Runtime Hardening | Phase 3.1 stdio protocol skeleton / Phase 3.2 tools/list mapping / Phase 3.3 tools/call integration / Phase 3.4 lifecycle hardening / Phase 3.5 release cleanup; default MCP_MODE=fake unchanged; real mode requires explicit command + allowlist; verified with 582 passed tests |
| **v2.3.0** | LLM Provider + Guardrails Runtime | Phase 4.1 LiteLLMProvider 硬化 / Phase 4.2 NL2SQL 真实 LLM 生成链路 + 结构化校验 + fallback / Phase 4.3 可选 LLMJudgeProvider + 评测元数据 / Phase 4.4 Guardrails 编排 + PII 脱敏防泄漏 / Phase 4.5 预算+缓存+降级闭环；默认 fake/offline，默认测试不调用真实 LLM；verified with 636 passed tests |
| **v2.4.0** | Operator Console Pilot | 试点级运营台闭环（Dashboard / Tasks / Approvals / Trace / Audit / Metrics / RBAC / Tools / NL2SQL）+ Docker demo scripts；默认离线可跑；前端工具调用仍受后端策略与审批约束；verified with 638 passed tests |
| **v2.5.0** | Real LLM Optional Acceptance Pack | Phase 5.1 provider preflight / Phase 5.2 opt-in real LLM smoke / Phase 5.3 token/cost/budget/cache/fallback 验收 / Phase 5.4 LLMJudge opt-in smoke / Phase 5.5 文档与 release prep；默认 fake/offline，默认测试不调用真实 LLM |
| **v2.6.0** | Phase 6.0 Engineering Readiness | 部署门禁（deployment guard）/ 生产模板（.env.production.example + compose override）/ prod 脚本 / CI 工程化增强；定位企业内网试点准生产可投入使用；默认离线路径不变 |
| **v2.7.0** | Production Security Baseline | Phase 7.1 CORS + 安全响应头 / Phase 7.2 request size limit + rate limit + basic abuse guard / Phase 7.3 结构化日志与脱敏 / Phase 7.4 审计留存与 JSONL 导出边界 / Phase 7.5 OIDC/SSO 最小接入骨架与配置预检；默认 fake/offline，默认测试不调用真实 LLM |
| **v2.8.0** | Controlled Real LLM Pilot | `/llm/preflight` 状态观测 + 前端 `/llm` 试点页 / acceptance_summary 统一口径 / budget-cache-fallback 行为收敛 / LLMJudge opt-in 收敛 / 审计日志指标联动；默认 fake/offline，默认 pytest/CI 不调用真实 LLM |
| **v2.9.0** | Real LLM Controlled Pilot Evidence | Phase 9.1~9.4：试点报告 schema/writer、opt-in smoke 自动生成脱敏报告、NL2SQL/Judge/audit/metrics 证据串联、pilot evidence 只读 API 与前端只读入口；默认 fake/offline，默认 pytest/CI 不调用真实 LLM |

---

## 项目结构

```
project-b-multi-agent/
├── app/
│   ├── api/                        # API 路由层
│   │   ├── tasks.py                #   任务创建（keyword/nl2sql/multitool/multi_agent/auto）
│   │   ├── nl2sql.py               #   NL2SQL 预览与执行
│   │   ├── tools.py                #   工具列表与调用
│   │   ├── approvals.py            #   审批管理
│   │   ├── approval_ui.py          #   审批 UI API
│   │   ├── audit.py                #   审计查询
│   │   ├── metrics.py              #   运行时指标
│   │   ├── bad_cases.py            #   BadCase 评测
│   │   ├── eval_summary.py         #   评测汇总
│   │   ├── multi_agent_eval.py     #   Multi-Agent 评测
│   │   ├── observability.py        #   可观测性 API
│   │   ├── memory_api.py           #   短期记忆 API
│   │   ├── skills_api.py           #   技能匹配 API
│   │   ├── reflection_api.py       #   自检 API
│   │   └── runtime_snapshot.py     #   运行时快照
│   ├── auth/                        # 认证与授权
│   │   ├── models.py                #   UserRole / User / TokenPayload
│   │   ├── password.py              #   bcrypt 哈希与验证
│   │   ├── jwt.py                   #   JWT 创建与解码
│   │   └── dependencies.py          #   RBAC 依赖（get_current_user / require_roles）
│   ├── cache/                       # 缓存层
│   │   └── redis_client.py          #   Redis 客户端 / NoopRedisClient
│   ├── agent/                      # Agent 内核层
│   │   ├── graph/                  #   LangGraph 有向图
│   │   │   └── kernel.py           #     AgentKernel（主链路编排）
│   │   ├── nodes/                  #   图节点
│   │   │   ├── planner.py          #     KeywordPlanner
│   │   │   └── multitool_planner.py#     MultiToolPlanner
│   │   ├── nl2sql/                 #   NL2SQL 模块
│   │   │   ├── metadata.py         #     SchemaMetadataExtractor
│   │   │   ├── pruner.py           #     SchemaPruner
│   │   │   ├── sql_guard.py        #     SQLGuard
│   │   │   ├── generator.py        #     MockNL2SQLGenerator
│   │   │   ├── llm_generator.py    #     LLMNL2SQLGenerator
│   │   │   ├── provider.py         #     LLMProvider / FakeLLMProvider / LiteLLMProvider
│   │   │   ├── executor.py         #     SQLiteReadOnlyExecutor
│   │   │   └── formatter.py        #     SQLResultFormatter
│   │   ├── multi_agent/            #   Multi-Agent 编排
│   │   │   ├── coordinator.py      #     CoordinatorAgent
│   │   │   ├── analyst.py          #     AnalystAgent
│   │   │   ├── executor.py         #     ExecutorAgent
│   │   │   ├── reviewer.py         #     ReviewerAgent
│   │   │   ├── orchestrator.py     #     MultiAgentOrchestrator
│   │   │   └── types.py            #     Multi-Agent 数据类型
│   │   ├── roles/                  #   Agent 角色
│   │   └── skills/                 #   Agent 技能
│   ├── harness/                    # Harness Runtime 层
│   │   ├── context/                #   上下文组装
│   │   │   └── assembler.py        #     ContextAssembler
│   │   ├── gateway/                #   工具网关
│   │   │   └── tool_gateway.py     #     ToolGateway
│   │   ├── hooks/                  #   Hook 管线
│   │   │   └── pipeline.py         #     HookPipeline
│   │   ├── policy/                 #   策略引擎
│   │   │   ├── engine.py           #     PolicyEngine
│   │   │   └── operation_whitelist.py #  OperationWhitelist
│   │   ├── security/               #   安全防线
│   │   │   └── injection_guard.py  #     PromptInjectionGuard
│   │   ├── trace/                  #   追踪记录
│   │   │   └── recorder.py         #     TraceRecorder
│   │   ├── audit/                  #   审计日志
│   │   │   └── recorder.py         #     AuditRecorder
│   │   ├── metrics/                #   运行时指标
│   │   │   ├── runtime_metrics.py  #     RuntimeMetricsRecorder
│   │   │   └── metrics_store.py    #     SQLiteMetricsStore
│   │   ├── eval/                   #   评测模块
│   │   │   ├── cases.py            #     NL2SQL 评测用例
│   │   │   ├── nl2sql_runner.py    #     NL2SQL EvalRunner
│   │   │   ├── multi_agent_runner.py #   Multi-Agent EvalRunner
│   │   │   ├── bad_cases.py        #     BadCase 数据模型
│   │   │   ├── bad_case_runner.py  #     BadCaseRunner
│   │   │   └── judge.py            #     FakeJudge / LLMJudgeProvider
│   │   ├── memory/                 #   短期记忆
│   │   │   └── short_term.py       #     ShortTermMemory
│   │   ├── skills/                 #   技能注册
│   │   │   └── registry.py         #     SkillRegistry
│   │   └── reflection/             #   自检反思
│   │       └── self_check.py       #     SelfCheckEngine
│   ├── tools/                      # 工具层
│   │   ├── local/                  #   本地工具
│   │   │   └── ops_query.py        #     5 个运营查询工具
│   │   └── mcp/                    #   MCP 工具
│   │       ├── client.py           #     FakeMCPClient
│   │       └── stdio_client.py     #     StdioMCPClient
│   ├── models/                     # 数据模型
│   │   └── schemas.py              #   Pydantic v2 模型
│   ├── services/                   # 业务服务
│   │   ├── nl2sql_pipeline.py      #   NL2SQL Pipeline
│   │   ├── multitool_pipeline.py   #   MultiTool Pipeline
│   │   └── approval_resume.py      #   Approval Resume Service
│   ├── storage/                    # 持久化存储
│   │   ├── task_store.py           #   SQLiteTaskStore
│   │   ├── approval_store.py       #   SQLiteApprovalStore
│   │   ├── audit_store.py          #   SQLiteAuditStore
│   │   ├── database.py              #   SQLAlchemy engine / session factory
│   │   ├── user_store.py            #   InMemoryUserStore
│   │   ├── base.py                  #   Store Protocol 定义
│   │   ├── models.py                #   SQLAlchemy ORM models
│   │   ├── factory.py               #   Store Factory
│   │   └── postgres/                #   PostgreSQL Store 实现
│   │       ├── task_store.py        #     PostgresTaskStore
│   │       ├── approval_store.py    #     PostgresApprovalStore
│   │       ├── audit_store.py       #     PostgresAuditStore
│   │       └── metrics_store.py     #     PostgresMetricsStore
│   ├── visualization/              # 可视化
│   │   └── chart_planner.py        #   ChartPlanner
│   ├── prompts/                    # Prompt 模板
│   │   └── nl2sql_prompt.md        #   NL2SQL Prompt
│   ├── core/                       # 核心配置
│   │   └── config.py               #   Settings
│   └── main.py                     # FastAPI 应用入口
├── alembic.ini                      # Alembic 配置
├── alembic/                         # Alembic 迁移
│   ├── env.py                       #   Alembic env
│   ├── script.py.mako               #   迁移模板
│   └── versions/                    #   迁移版本
│       └── 001_initial.py           #     初始迁移（7 张表）
├── data/
│   ├── db/                         # SQLite 数据库
│   │   ├── ops_demo.sqlite         #   运营 demo 数据
│   │   ├── runtime.sqlite          #   运行时数据
│   │   └── runtime_metrics.sqlite  #   指标数据
│   └── evaluation/                 # 评测数据
│       ├── nl2sql_cases.json       #   NL2SQL 评测用例
│       ├── multi_agent_cases.json  #   Multi-Agent 评测用例
│       └── bad_cases.json          #   BadCase 回归集
├── docs/                           # 文档
├── scripts/                        # 脚本
│   ├── init_demo_db.py             #   初始化 demo 数据库
│   ├── start_dev.py                #   开发启动脚本
│   └── check_health.py             #   健康检查
├── tests/                          # 测试（730+ 个）
├── .github/workflows/ci.yml        # CI 配置
├── Dockerfile                      # Docker 镜像
├── docker-compose.yml              # Docker Compose
├── pyproject.toml                  # 项目配置
└── .env.example                    # 环境变量示例
```

---

## 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| **Web 框架** | FastAPI | 异步 API，自动 OpenAPI 文档 |
| **数据校验** | Pydantic v2 | 类型安全的数据模型与校验 |
| **存储** | SQLite / PostgreSQL | 轻量级本地存储（默认）+ 企业级 PostgreSQL 存储（试点） |
| **ORM / 迁移** | SQLAlchemy + Alembic | 数据库抽象 + 版本化迁移 |
| **缓存** | Redis | 审批状态缓存 / session 存储（默认 NoopRedisClient） |
| **认证** | PyJWT + bcrypt | JWT Bearer Token + bcrypt 密码哈希 |
| **授权** | RBAC | 4 角色（admin / operator / viewer / auditor）+ 端点权限 |
| **Agent 编排** | LangGraph | 有向图 Agent 内核，实现 START → ... → END 编排 |
| **工具协议** | MCP | Model Context Protocol，统一本地与远程工具调用 |
| **LLM 接入** | LiteLLM（可选） | 可插拔 LLM Provider，默认 FakeLLMProvider 零依赖 |
| **测试** | pytest + httpx | 754 passed, 4 skipped（默认 real_llm 用例 skip） |
| **容器化** | Docker + Docker Compose | 一键启动，健康检查 |

---

## 后续 Roadmap

| 方向 | 说明 |
|------|------|
| **真实外部 MCP Server 验收** | 当前 real MCP stdio 协议链路已完成（基于 fake fixture 验收）；真实外部 MCP Server 生产验收与更完整 sandbox 仍在后续阶段 |
| **完整 LangGraph native checkpoint / Command resume** | 当前已有 graph checkpoint / interrupt / resume adapter 最小闭环；完整 LangGraph native checkpoint、Command interrupt、Command resume 仍在 Roadmap |
| **真实 LLM provider eval** | LiteLLMProvider 接入真实 LLM API，运行完整 NL2SQL / Multi-Agent eval |
| **试点级运营台/审批台前端** | 已完成 v2.4.0 试点级交付（非生产级交付） |
| **LLM-as-Judge 生产验收** | LLMJudgeProvider 真实 provider 路径在真实环境完成稳定性与成本验收，并补齐评测治理策略 |
| **LLM 自主多 Agent 规划** | 从确定性多角色编排升级为 LLM 自主决策的多 Agent 协作 |
| **长期记忆 / 向量库** | 从 ShortTermMemory 升级为持久化 + 向量检索的长期记忆 |
| **持久化 Skill Learning** | 从规则型 SkillRegistry 升级为可学习、可持久化的技能系统 |
| **Cost Dashboard 前端** | 基于成本 API 构建可视化看板 |
| **50+ BadCase** | 扩展回归集到 50+ case，覆盖更多边界场景 |

---

## v2.4 / v2.5 / v2.6 阶段进展（增量说明）

- **v2.4.1**：完成前端壳与任务中心最小闭环（任务创建、列表、详情、Trace 入口）。
- **v2.4.2**：完成审批台闭环（审批列表、审批详情、approve/reject/resume）。
- **v2.4.3**：完成 Trace / Audit / Metrics 聚合展示。
- **v2.4.4**：完成 RBAC 试点说明页与 Docker 本地演示脚本（`scripts/demo_up.ps1`、`scripts/demo_smoke.ps1`、`scripts/demo_down.ps1`）。
- **v2.4.5**：完成 Tools + NL2SQL 试点页（工具筛选与最小调用验证、NL2SQL preview/execute 页面）。
- **v2.5.0**：完成真实 LLM 可选验收包收口（Provider preflight、opt-in real LLM smoke、token/cost/budget/cache/fallback 验收、LLMJudge opt-in smoke、报告模板与 release prep 文档）。
- **v2.6.0**：完成 Phase 6.0 工程化落地（deployment guard、/deployment/check、生产模板 compose override、prod 脚本、CI 工程化增强）。
- **v2.7.0**：完成 Production Security Baseline 阶段交付（Phase 7.1~7.5：CORS/安全响应头、请求防护、结构化日志脱敏、审计留存与导出边界、OIDC/SSO 最小接入骨架与配置预检），当时基线 727 passed, 4 skipped（历史记录）。

### RBAC 试点口径

- 默认演示路径保持不变：`AUTH_ENABLED=false`、`RBAC_ENABLED=false`。
- 启用权限试点需显式设置：`AUTH_ENABLED=true`、`RBAC_ENABLED=true`。
- 当前仅做试点级权限说明与页面收敛，不实现生产登录系统。

### v2.9.0 阶段定位（历史）

- v2.9.0 阶段目标为“Real LLM Controlled Pilot Evidence（受控试点证据）能力交付”。
- 默认开发/演示路径保持不变，仍可离线运行。
- 生产形态通过 `docker-compose.prod.yml` override 与 `scripts/prod_*.ps1` 执行。
- v2.7 Phase 7.1 已实现 CORS 与安全响应头基线：development 默认允许 `http://localhost:3000`，production 需显式配置允许来源且禁止 `*`。
- v2.7 Phase 7.2 已实现请求防护基线：rate limit、request size limit、basic abuse guard（当前限流为进程内内存版，适合单实例内网试点）。
- v2.7 Phase 7.3 已实现结构化日志与日志脱敏：默认不记录 prompt 原文/密钥原文。
- v2.7 Phase 7.4 已实现审计留存策略与 JSONL 导出边界：默认脱敏，不导出 prompt 原文和密钥原文。
- v2.7 Phase 7.5 已实现 OIDC/SSO 最小接入骨架与配置预检：默认关闭，不依赖真实外部 IdP。

### v3.1 产品化增强路线（发布后收口）

- v3.1 产品化增强路线分阶段推进，Phase 11.1~11.5 已完成，**v3.1.0 tag 与 GitHub Release 已完成**。
- 默认开发模板继续使用 `docker-compose.yml`（离线演示友好，auth/rbac 默认关闭）。
- 生产 override 模板使用 `docker-compose.yml + docker-compose.prod.yml`（启用生产门禁所需配置约束）。
- 推荐运维脚本：
  - `powershell -ExecutionPolicy Bypass -File scripts/prod_config_check.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/prod_up.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/prod_smoke.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/prod_down.ps1`

### v3.1.0 发布后收口（当前）

- v3.1.0 Productization Enhancement 已发布完成（tag 与 GitHub Release 已完成，tag 保持不变）。
- Phase 11.1~11.5 已完成文档化收口：离线 demo seed 与 E2E 演示脚本、只读运营总览、真实 LLM opt-in 执行记录（本轮 skipped）、OIDC 最小真实 IdP 演练、运维排障索引与备份恢复清单。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM，本轮未执行真实外网 LLM。
- 当前全量基线：`754 passed, 4 skipped`。

### 仍保持的边界

- 不宣称生产级 SSO/OIDC 已完成（Phase 7.5 仅为最小接入骨架与配置预检）。
- 不宣称多租户已完成。
- 不宣称复杂 BI 已完成。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不接真实外部 MCP / 真实 LLM 作为默认演示依赖。
- 前端工具调用不会绕过后端 ToolGateway / PolicyEngine / 审批链路。
- NL2SQL 默认 mock/fake；真实 LLM 仅可选配置，不进入默认验收。

## v2.7 Phase 7.5：OIDC/SSO 最小接入骨架

- 已新增 OIDC 配置骨架与 `/auth/oidc/status` 状态接口（仅返回配置状态，不返回 client_secret 原文）。
- 默认 `OIDC_ENABLED=false`，不依赖真实外部 IdP，不影响默认离线演示路径。
- 生产启用 OIDC 时需配置 issuer/client_id/redirect_uri/client_secret env，且要求 https。
- 角色映射仅允许 `admin/operator/viewer/auditor`，未命中回退 `viewer`。
- 当前仅为最小接入骨架与配置预检，不宣称生产级 SSO/OIDC 已完成。

## v2.9.0 Real LLM Controlled Pilot Evidence（历史阶段）

- v2.9 已完成受控试点证据阶段交付，默认路径保持 fake/offline。
- 默认 pytest 与默认 CI 不调用真实 LLM；真实 LLM smoke 仅 opt-in 验收。
- 已提供 `/llm/pilot/reports` 只读审查 API 与前端 LLM 页 Pilot Evidence 只读区域，用于受控试点证据查看。
- 验收摘要统一字段：provider/model、real_call_attempted、fallback_reason、tokens/cost、budget_action、cache_hit、request_id、error_type。
- 审计导出与试点报告均默认脱敏，不导出 prompt 原文、API key/token/password/secret/数据库密码原文。
- 不宣称真实 LLM 生产验收完成，不宣称公网生产可直接上线。

### v2.8.0 / v2.9.0 / v3.0.0 与 v3.1.0 版本关系

- v2.8.0 GitHub Release 已由用户手动创建（tag 不移动）。
- v2.9.0 GitHub Release 已由用户手动创建（tag 不移动）。
- v3.0.0 Final Production Landing 已发布完成（tag 与 GitHub Release 均已完成且保持不变）。
- v3.0.0 阶段保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；未将真实外网 LLM 纳入默认流程。
- 当前 main 进入 v3.1.0 Productization Enhancement release prep，聚焦 Phase 11.1~11.5 收口与发布材料归档。
- v3.0 规划文档：`docs/v3_final_production_landing_plan.md`。
- v3.0 Phase 10.1 已建立执行记录模板：`docs/real_llm_pilot_execution_log_v30.md`（本轮未执行真实外网 LLM，待手动 opt-in）。
- v3.0 Phase 10.2 已建立生产部署演练与回滚记录：`docs/production_deployment_drill_v30.md`（本地/内网试点模拟，不等于公网生产上线）。
- v3.0 Phase 10.3 已建立运维监控与备份恢复演练记录：`docs/operations_monitoring_backup_drill_v30.md`（runbook 级演练，不引入复杂运维平台）。
- v3.0 Phase 10.4 已建立安全复核与 Go/No-Go 评审：`docs/security_go_no_go_review_v30.md`（建议企业内网试点 Go，公网直上 No-Go）。
- v3.0.0 发布材料：`RELEASE_NOTES_v3.0.0.md`、`docs/release_review_v3.0_final_production_landing.md`（历史归档）。
- v3.1 规划文档：`docs/v3_1_productization_enhancement_plan.md`。
- v3.1 Phase 11.1 已落地离线演示 seed 与 E2E 脚本：
  - `scripts/demo_seed_data.py`
  - `scripts/demo_e2e.ps1`
  - `docs/demo_e2e_runbook_v31.md`
- v3.1 Phase 11.2 已落地只读运营总览入口：
  - 后端只读聚合 API：`GET /operations/summary`
  - 前端只读页面：`/operations`
  - 汇总 health/deployment/metrics/audit/tasks/approvals/pilot reports/demo evidence，且保持脱敏边界
- v3.1 Phase 11.3 已建立真实 LLM opt-in 执行记录：`docs/real_llm_pilot_execution_log_v31.md`
  - 本轮因 opt-in 环境变量缺失记录 `skipped`
  - 未执行真实外网 LLM，未生成伪造成功报告，待用户手动注入环境后重试
- v3.1 Phase 11.4 已建立 OIDC/SSO 最小真实 IdP 配置演练文档：
  - `docs/oidc_minimal_idp_drill_v31.md`
  - 仅用于最小配置演练与排障，不等于生产级 SSO/OIDC 完成
- v3.1 Phase 11.5 已完成运维 polish 文档收口：
  - 运维排障索引：`docs/operations_troubleshooting_index_v31.md`
  - 备份恢复检查清单：`docs/backup_restore_checklist_v31.md`
  - 以 runbook/checklist 为主，不引入破坏性清理流程，不删除用户数据
- v3.1.0 发布材料：`RELEASE_NOTES_v3.1.0.md`、`docs/release_review_v3.1_productization_enhancement.md`、`docs/post_release_check_v3.1.0.md`。
- v3.0.0 / v3.1.0 tag 与对应 GitHub Release 已完成且保持不变；main 超前 tag 属于发布后文档收口。
- 后续建议进入 v3.2 或下一阶段路线规划（持续保持边界：不宣称公网直上、不宣称真实 LLM 生产验收完成）。
- v3.2 规划已开启：`docs/v3_2_acceptance_observability_plan.md`（当前版本仍为 3.1.0，不改版本号、不打 tag、不创建 Release）。
- v3.2 Phase 12.1 已新增 Acceptance Snapshot 能力：
  - 脚本：`scripts/acceptance_snapshot.py`
  - runbook：`docs/acceptance_snapshot_runbook_v32.md`
  - 输出：`docs/reports/acceptance_snapshots/*.json` + `*.md`
  - 默认 fake/offline，不触发真实 LLM；服务未启动时在线检查标记 skipped

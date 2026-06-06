# Project B: Harness-native 运营中台 Agent

## v3.7 Phase 17.4 Store and Redis production readiness drill（当前已完成）

- 新增 runbook：`docs/store_redis_readiness_drill_v37.md`。
- 新增只读演练脚本：`scripts/store_redis_readiness_drill.py`，默认输出 `docs/reports/store_redis_readiness_drill/`。
- 新增测试：`tests/test_store_redis_readiness_drill_v374.py`。
- 演练覆盖 PostgreSQL Store opt-in、Store Factory、SQLite fallback、Alembic migration precheck、Redis opt-in、NoopRedisClient fallback、进程内限流边界、deployment guard、审计/指标 store 边界和 compose readiness。
- 输出明确 `database_connected=false`、`redis_connected=false`、`migration_executed=false`、`business_data_written=false`、`audit_data_written=false`、`metrics_data_written=false`。
- 本阶段不连接真实 PostgreSQL/Redis，不执行 Alembic migration，不写业务/审计/指标数据，不读取或输出 `DATABASE_URL`、`REDIS_URL`、`JWT_SECRET` 等 secret 原文。
- 当前仍不宣称 PostgreSQL、Redis 或多实例限流生产验收完成；Phase 17.5 与 v3.7.0 release prep 已完成，tag/Release 待用户单独确认。

## v3.7 Phase 17.5 Business system integration safety checklist（当前已完成）

- 新增 runbook：`docs/business_system_integration_safety_checklist_v37.md`。
- 新增只读安全清单脚本：`scripts/business_system_integration_safety_checklist.py`，默认输出 `docs/reports/business_system_integration_safety/`。
- 新增测试：`tests/test_business_system_integration_safety_checklist_v375.py`。
- 清单覆盖业务系统 opt-in、secret target、ToolGateway/PolicyEngine/OperationWhitelist、allowlist 与超时、写入边界、审批恢复、审计证据、request/prompt safety、回滚与失败恢复证据。
- 输出明确 `business_system_connected=false`、`business_read_executed=false`、`business_write_executed=false`、`business_data_written=false`、`approval_bypassed=false`、`audit_bypassed=false`。
- 本阶段不连接真实业务系统，不执行真实读写，不创建/更新/删除业务数据，不读取或输出 token/API key/client_secret/业务系统 URL 原文。
- 当前仍不宣称真实业务系统生产集成验收完成；建议下一阶段进入 Phase 17.6 v3.7 release prep。

## v3.7.0 release prep（当前已完成）

- 版本已同步到 `3.7.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、v3.7 脚本 version markers、相关测试断言。
- 已新增 `RELEASE_NOTES_v3.7.0.md`。
- 已新增 `docs/release_review_v3.7_external_integration_real_provider_acceptance.md`。
- Phase 17.1~17.5 纳入 v3.7.0 release prep 范围。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；默认不连接真实外部 MCP、真实业务系统、真实 PostgreSQL、真实 Redis 或真实 IdP。
- 不宣称公网生产可直接上线，不宣称真实 LLM/MCP/PostgreSQL/Redis/业务系统生产验收完成，不宣称生产级 SSO/OIDC、多租户或复杂 BI 全量完成。

> **Harness Runtime** + **LangGraph Agent Kernel** + **MCP Tool Gateway** — 生产级运营 Agent 工程化框架

> **⚠️ 边界说明（请务必阅读）**
>
> 本项目是 **production-grade Agent Harness engineering prototype**。当前 Multi-Agent 是 **deterministic multi-role orchestration**，不是完全自治多 Agent；当前已实现 real MCP stdio protocol path（基于 fake stdio fixture 验收），并提供 LiteLLMProvider/LLMJudgeProvider 可选真实 provider 路径（默认 fake/offline，默认测试不调用真实 LLM），但真实外部 MCP Server 与真实 LLM 生产验收仍需外部环境和密钥单独完成。当前已实现 graph checkpoint / interrupt / resume adapter 最小闭环，完整 LangGraph native checkpoint / Command interrupt / Command resume 仍在 Roadmap。

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue)](.github/workflows/ci.yml) [![Python](https://img.shields.io/badge/Python-3.11+-blue)](pyproject.toml) [![Tests](https://img.shields.io/badge/Tests-900%20passed%20(4%20skipped)-passing-brightgreen)](tests/) [![Version](https://img.shields.io/badge/Release_Prep-v4.3.0-yellow)]()

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

当前基线：**920 passed, 4 skipped**，覆盖全部模块：

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
├── tests/                          # 测试（920+ 个）
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
| **测试** | pytest + httpx | 920 passed, 4 skipped（默认 real_llm 用例 skip） |
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

### v3.1.0 发布后收口（历史）

- v3.1.0 Productization Enhancement 已发布完成（tag 与 GitHub Release 已完成，tag 保持不变）。
- Phase 11.1~11.5 已完成文档化收口：离线 demo seed 与 E2E 演示脚本、只读运营总览、真实 LLM opt-in 执行记录（本轮 skipped）、OIDC 最小真实 IdP 演练、运维排障索引与备份恢复清单。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM，本轮未执行真实外网 LLM。
- 当前全量基线：`920 passed, 4 skipped`。

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
- 当前 main 超前 `v3.1.0` tag，进入 v3.2.0 Acceptance & Observability Enhancement release prep。
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
- v3.2 规划与收口文档：`docs/v3_2_acceptance_observability_plan.md`（当前版本为 3.2.0 release prep，不打 tag、不创建 Release）。
- v3.2 Phase 12.1 已新增 Acceptance Snapshot 能力：
  - 脚本：`scripts/acceptance_snapshot.py`
  - runbook：`docs/acceptance_snapshot_runbook_v32.md`
  - 输出：`docs/reports/acceptance_snapshots/*.json` + `*.md`
  - 默认 fake/offline，不触发真实 LLM；服务未启动时在线检查标记 skipped


- v3.2 Phase 12.3 added Demo artifact bundle:
  - script: `scripts/demo_e2e.ps1` (supports `-ArtifactDir`, default `docs/reports/demo_artifacts/`)
  - helper: `scripts/demo_artifact_bundle.py`
  - runbook: `docs/demo_artifact_bundle_runbook_v32.md`
  - each run creates a timestamped artifact folder with `demo_e2e_summary.json` / `online_smoke_result.json` / `seed_summary.json` / `pilot_report_index.json` / acceptance snapshot
  - when service is unavailable, online smoke is marked skipped and does not report false success
- v3.2 Phase 12.2 operations observability polish completed:
  - `/operations` read-only overview now highlights health/deployment/metrics/tasks/approvals/audit/pilot reports/demo evidence with clearer empty/error/skipped states.
  - Adds read-only hints for acceptance snapshot and demo artifact bundle runbooks + default artifact/snapshot directories.
  - Boundary kept: fake/offline default, no real LLM call, no secrets, no public-production claim.
- v3.2 Phase 12.4 added Failure Diagnostics Pack:
  - runbook: `docs/failure_diagnostics_pack_v32.md`
  - script: `scripts/failure_diagnostics.py` (read-only diagnostics, JSON + Markdown output)
  - default output dir: `docs/reports/failure_diagnostics/`
  - covers compose/deployment guard/OIDC/audit export/demo_e2e skipped/acceptance snapshot skipped/pilot reports empty/real LLM opt-in skipped
  - service unavailable is marked skipped without false success; no write/delete operation
- v3.2 Phase 12.5 optional real LLM evidence retry:
  - execution log: `docs/real_llm_optional_retry_log_v32.md`
  - this round status: `skipped` (missing opt-in env, no real external LLM executed)
  - no real-external pilot report generated in this round
- v3.2.0 release prep artifacts:
  - `RELEASE_NOTES_v3.2.0.md`
  - `docs/release_review_v3.2_acceptance_observability.md`
  - historical note: release prep round did not create tag/Release in that step
- v3.2.0 tag and GitHub Release are now completed (manual Release by user); tag remains unchanged.
- Next recommended direction: move into v3.3 or next-stage planning while keeping current boundaries.
- v3.3 planning is now opened:
  - `docs/v3_3_operational_automation_governance_plan.md`
  - scope: operational automation + governance workflow convergence (read-only first)
  - current app version remains `3.2.0`; no new tag/release in this planning step
- v3.3 Phase 13.1 (Report index & retention) completed:
  - script: `scripts/report_index.py`
  - test: `tests/test_report_index_v331.py`
  - runbook: `docs/report_index_retention_runbook_v33.md`
  - default output: `docs/reports/report_index/`
  - read-only only: stale candidates are listed, no deletion is executed
- v3.3 Phase 13.2 (Config drift checklist) completed:
  - script: `scripts/config_drift_check.py`
  - test: `tests/test_config_drift_v332.py`
  - runbook: `docs/config_drift_checklist_v33.md`
  - default output: `docs/reports/config_drift/`
  - read-only only: checks key drift/warnings, no `.env` mutation, no secret value output

- v3.3 Phase 13.3 (Governance policy summary) completed:
  - script: `scripts/governance_policy_summary.py`
  - test: `tests/test_governance_policy_summary_v333.py`
  - governance entry doc: `docs/governance_policy_summary_v33.md`
  - default output: `docs/reports/governance_policy/`
  - read-only only: governance summary/report output, no runtime mutation, no real external LLM execution

- v3.3 Phase 13.4 (Operations automation script polish) completed:
  - runbook: `docs/operations_automation_scripts_v33.md`
  - consistency test: `tests/test_operations_automation_scripts_v334.py`
  - polished scripts: acceptance/demo artifact/failure diagnostics/report index/config drift/governance summary/demo_e2e
  - alignment: common summary keys + CLI/default output semantics clarified (read-only boundary preserved)

## v3.3 Phase 13.5 (Optional live drill window)

- Added runbook: `docs/live_drill_window_v33.md`.
- Added read-only precheck script: `scripts/live_drill_window.py` (default output `docs/reports/live_drill_window/`).
- Added test: `tests/test_live_drill_window_v335.py`.
- Default remains fake/offline; default pytest/CI does not execute real external LLM.
- Missing opt-in conditions must be recorded as `skipped` (or `partial/blocked` with missing list), never faked as success.

## v3.3.0 release prep (current)

- Current release-prep version is `3.3.0`.
- v3.3.0 focus: Operational Automation & Governance (Phase 13.1~13.5).
- Release-prep docs:
  - `RELEASE_NOTES_v3.3.0.md`
  - `docs/release_review_v3.3_operational_automation_governance.md`
- Boundaries remain enforced: fake/offline default, pytest/CI default no real LLM, live drill read-only precheck, missing opt-in => skipped.
- This round does **not** create v3.3.0 tag and does **not** create GitHub Release.

## v3.3.0 release-created closure (current)

- GitHub Release for `v3.3.0` has been manually created by user.
- Release title: `Project B v3.3.0 - Operational Automation & Governance`.
- Release notes source: `RELEASE_NOTES_v3.3.0.md`.
- Tag remains unchanged: `v3.3.0^{}` = `0399b84de5c2232a451d02ef37a8b181d0b01ebe`.
- Historical tags remain unchanged:
  - `v3.2.0^{}` = `3c12985d15062328efe5711ee939ca28ba4dbacf`
  - `v3.1.0^{}` = `4ffb8044ccc0f1fb62c570308c8c9c4c8c46a99a`
  - `v3.0.0^{}` = `fa5b07b3ffb373d2f1060f38b6ef0a4d31b5194d`
- No real external LLM executed in this closure round.
- Default fake/offline and default pytest/CI no-real-LLM boundaries remain.
- main ahead of tag belongs to post-release documentation closure.
- Next suggested direction: move into v3.4 (or next-stage) roadmap planning.

## v3.4 路线规划（历史）

- 新规划文档：`docs/v3_4_pilot_hardening_operator_experience_plan.md`。
- v3.4 定位：Pilot Hardening & Operator Experience。
- 当前版本已在 v3.4.0 release prep 阶段同步为 `3.4.0`。
- `v3.3.0` GitHub Release 已完成，tag 保持不变。
- 边界保持不变：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，默认不执行真实外网 LLM。
- 不宣称公网生产直上，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 已完成，不宣称多租户/复杂 BI 全量完成。
- Phase 14.1~14.6 已完成并进入 v3.4.0 发布收口。

## v3.4 Phase 14.1 操作员工作流收口（已完成）

- 新增操作员工作流文档：`docs/operator_workflow_polish_v34.md`。
- 新增只读索引脚本：`scripts/operator_workflow_index.py`，默认输出 `docs/reports/operator_workflow/`。
- 新增测试：`tests/test_operator_workflow_index_v341.py`。
- 覆盖入口：`/operations`、acceptance snapshot、demo artifact bundle、failure diagnostics、report index、config drift、governance summary、live drill window。
- 每个入口均记录使用时机、默认输出目录、只读边界、真实 LLM 执行边界、失败或 skipped 解释。
- 保持只读边界：不删除数据、不自动清理报告、不修改 `.env`、不执行真实外网 LLM。

## v3.4 Phase 14.2 故障演练包（已完成）

- 新增故障演练文档：`docs/incident_rehearsal_pack_v34.md`。
- 新增只读演练脚本：`scripts/incident_rehearsal_pack.py`，默认输出 `docs/reports/incident_rehearsal/`。
- 新增测试：`tests/test_incident_rehearsal_pack_v342.py`。
- 覆盖服务不可用、compose/prod compose、deployment check、operations、acceptance/demo skipped、failure diagnostics、report index、config drift、governance/live drill、OIDC secret env、real LLM opt-in 缺失等场景。
- 状态词限定为 `success / skipped / blocked / partial / failed`，缺少 opt-in 条件必须 `skipped`。
- 保持只读边界：默认不启动服务、不修改环境、不执行真实外网 LLM、不删除数据、不自动清理报告。

## v3.4 Phase 14.3 证据归档 Manifest（已完成）

- 新增证据归档文档：`docs/evidence_archive_manifest_v34.md`。
- 新增只读 manifest 脚本：`scripts/evidence_archive_manifest.py`，默认输出 `docs/reports/evidence_archive/`。
- 新增测试：`tests/test_evidence_archive_manifest_v343.py`。
- 统一索引 acceptance、demo、failure、report index、config drift、governance、live drill、operator workflow、incident rehearsal、release review、post release handoff 证据。
- 仅记录文件元数据，不读取报告内容，不删除文件，不自动执行 retention 清理。
- 空目录或缺失目录以 `skipped` 或 `warning` 表示，不伪造成成功。

## v3.4 Phase 14.4 可选集成准备度矩阵（已完成）

- 新增准备度矩阵文档：`docs/optional_integration_readiness_matrix_v34.md`。
- 新增只读矩阵脚本：`scripts/optional_integration_readiness.py`，默认输出 `docs/reports/optional_integration_readiness/`。
- 新增测试：`tests/test_optional_integration_readiness_v344.py`。
- 覆盖真实 LLM、OIDC、外部 MCP、Postgres、Redis、前端 build/network dependency、deployment guard、audit export/redaction readiness。
- 仅输出 env name 与 `present=true/false`，不读取或输出真实 secret 值。
- 不调用真实外网 LLM，不连接真实外部 MCP；缺少 opt-in 条件必须 `skipped`。

## v3.4 Phase 14.5 企业内网试点交接清单（已完成）

- 新增交接文档：`docs/pilot_handoff_checklist_v34.md`。
- 新增只读生成脚本：`scripts/pilot_handoff_checklist.py`，默认输出 `docs/reports/pilot_handoff/`。
- 新增测试：`tests/test_pilot_handoff_checklist_v345.py`。
- 覆盖 admin/operator/viewer/auditor 角色、RBAC 边界、OIDC 最小演练边界、real LLM skipped/ready 解释、演练与证据归档引用、备份恢复链接、已知限制。
- Go/No-Go：企业内网试点可继续，公网直上 No-Go，真实生产验收需另行执行。
- 保持只读边界：不读取 secret 原文、不执行真实外网 LLM、不写业务数据。

## v3.4.0 release prep（历史）

- release-prep 阶段版本已同步为 `3.4.0`。
- 新增发布材料：`RELEASE_NOTES_v3.4.0.md`、`docs/release_review_v3.4_pilot_hardening_operator_experience.md`。
- release notes 覆盖 Phase 14.1~14.5 与 skipped/blocked/partial 状态边界。
- release review 覆盖 scope、changed docs/scripts/tests/modules、verification matrix、security/privacy boundary、operational boundary、known limitations、Go/No-Go。
- release prep 当轮未打 `v3.4.0` tag，未创建 GitHub Release，未移动历史 tag。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM，release prep 当轮未执行真实外网 LLM。

## v3.4.0 release-created closure（已完成）

- GitHub Release `v3.4.0` 已由用户手动创建。
- Release 标题：`Project B v3.4.0 - Pilot Hardening & Operator Experience`。
- Release notes 来源：`RELEASE_NOTES_v3.4.0.md`。
- tag 保持不变：`v3.4.0^{}` = `868dd76496a08821dbb0a133cb28d0a62a51a5d7`。
- 历史 tag 保持不变：
  - `v3.3.0^{}` = `0399b84de5c2232a451d02ef37a8b181d0b01ebe`
  - `v3.2.0^{}` = `3c12985d15062328efe5711ee939ca28ba4dbacf`
  - `v3.1.0^{}` = `4ffb8044ccc0f1fb62c570308c8c9c4c8c46a99a`
  - `v3.0.0^{}` = `fa5b07b3ffb373d2f1060f38b6ef0a4d31b5194d`
- release-created 文档收口未执行真实外网 LLM。
- 默认 fake/offline 和默认 pytest/CI 不调用真实 LLM 边界保持不变。
- main 超前 tag 属于发布后文档收口。
- 后续建议进入 v3.5 或下一阶段路线规划。

## v3.5.0 release-created closure（当前）

- 规划文档：`docs/v3_5_controlled_pilot_expansion_plan.md`。
- 生产级后续路线图：`docs/enterprise_production_landing_roadmap.md`。
- v3.5 定位：Controlled Pilot Expansion & Evidence Operations。
- GitHub Release `v3.5.0` 已创建。
- Release 标题：`Project B v3.5.0 - Controlled Pilot Expansion & Evidence Operations`。
- Release notes 来源：`RELEASE_NOTES_v3.5.0.md`。
- 发布后检查：`docs/post_release_check_v3.5.0.md`。
- 远端 tag `v3.5.0` 指向 commit `90cf1b3a325032b6d865c82d11035c27cfee3017`，历史 tag 保持不变。
- 由于本机 `github.com:443` Git HTTPS 不通，本轮通过 GitHub API 创建远端 annotated tag/ref 与 Release；未移动、删除或重建远端 tag。
- 保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，默认不执行真实外网 LLM，不输出真实 secret 原文。
- 不宣称公网生产直上，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 或多租户/复杂 BI 全量完成。
- main 超前 `v3.5.0` tag 属于发布后文档收口。
- 后续建议进入 v3.6 Enterprise Identity & Tenant Boundary 或下一阶段路线规划。

## v3.5 Phase 15.1 试点证据对比快照（已完成）

- 新增 runbook：`docs/pilot_evidence_comparison_v35.md`。
- 新增只读对比脚本：`scripts/pilot_evidence_comparison.py`，默认输出 `docs/reports/pilot_evidence_comparison/`。
- 新增测试：`tests/test_pilot_evidence_comparison_v351.py`。
- 支持 baseline/current manifest JSON 或证据目录输入，仅读取元数据，不读取报告正文。
- 输出 JSON + Markdown，覆盖新增、减少、变化文件统计与 `warnings`。
- 保持只读边界：不删除、不移动、不修改输入证据，不自动执行 retention 清理，不读取或输出真实 secret 原文，不执行真实外网 LLM。

## v3.5 Phase 15.2 操作员演练评分 Rubric（已完成）

- 新增 runbook：`docs/operator_drill_scoring_rubric_v35.md`。
- 新增只读评分脚本：`scripts/operator_drill_scoring.py`，默认输出 `docs/reports/operator_drill_scoring/`。
- 新增测试：`tests/test_operator_drill_scoring_v352.py`。
- 评分维度覆盖 availability、recoverability、evidence_integrity、configuration_readiness、permission_boundary、known_limitations。
- 输入来源包括 incident rehearsal、pilot handoff、optional integration readiness、evidence comparison 的 JSON 元数据。
- 保持只读边界：不读取报告正文、不写业务数据、不自动改变 Go/No-Go 结论、不读取或输出真实 secret 原文、不执行真实外网 LLM。
- 建议下一执行入口：Phase 15.3 Controlled integration dry-run checklist。

## v3.5 Phase 15.3 受控集成 dry-run checklist（已完成）

- 新增 runbook：`docs/controlled_integration_dry_run_v35.md`。
- 新增只读 dry-run 脚本：`scripts/controlled_integration_dry_run.py`，默认输出 `docs/reports/controlled_integration_dry_run/`。
- 新增测试：`tests/test_controlled_integration_dry_run_v353.py`。
- 覆盖 real LLM、OIDC、external MCP、Postgres、Redis、frontend build/network、deployment guard、audit export redaction。
- 支持通过 `--readiness-report` 串联 Phase 14.4 optional integration readiness JSON，只消费结构化元数据。
- 保持只读边界：不启动服务、不修改 `.env`、不连接真实外部 MCP、不调用真实外网 LLM、不读取或输出真实 secret 原文。
- 生产级方向已新增独立路线图，但当前项目仍只能作为企业内网受控试点与准生产演示基础，不宣称生产级全量完成。
- 建议下一执行入口：Phase 15.4 Governance exception register。

## v3.5 Phase 15.4 治理例外登记（已完成）

- 新增 runbook：`docs/governance_exception_register_v35.md`。
- 新增只读治理例外登记脚本：`scripts/governance_exception_register.py`，默认输出 `docs/reports/governance_exceptions/`。
- 新增测试：`tests/test_governance_exception_register_v354.py`。
- 支持引用 config drift、governance policy summary、incident rehearsal、operator drill scoring 的 JSON 元数据。
- 例外字段覆盖风险描述、影响范围、责任人、到期时间、补偿控制、复核证据、状态和下一步动作。
- 保持只读边界：不自动批准例外、不绕过 deployment guard/安全响应头/审计脱敏/审批链路、不记录真实 secret 原文、不执行真实外网 LLM。
- Phase 15.4 交付当轮不改版本号、不打 tag、不创建 Release；当前版本已完成 `v3.5.0` 发布。
- 建议下一执行入口：Phase 15.5 Pilot closeout report pack。

## v3.5 Phase 15.5 试点收口报告包（已完成）

- 新增 runbook：`docs/pilot_closeout_report_pack_v35.md`。
- 新增只读收口报告包脚本：`scripts/pilot_closeout_report_pack.py`，默认输出 `docs/reports/pilot_closeout/`。
- 新增测试：`tests/test_pilot_closeout_report_pack_v355.py`。
- 支持汇总 pilot handoff、evidence archive、optional integration readiness、operator scoring、controlled integration dry-run、governance exception register 的 JSON 元数据。
- 报告包包含 executive summary、evidence summary、known limitations、Go/No-Go、next actions 和 boundary declarations。
- 保持 `skipped/blocked/partial` 原始语义，不把缺失或阻断项伪造成 `success`。
- 保持只读边界：不读取报告正文、不写业务数据、不执行真实外网 LLM、不输出真实 secret 原文。
- 当前版本已完成 `v3.5.0` 发布，tag 与 Release 已创建。

## v3.5 Phase 15.6 release prep（已完成）

- 已同步版本到 `3.5.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、脚本 version markers、相关测试断言。
- 已新增 `RELEASE_NOTES_v3.5.0.md`。
- 已新增 `docs/release_review_v3.5_controlled_pilot_expansion.md`。
- Phase 15.1~15.5 纳入 v3.5.0 release prep 范围。
- `v3.5.0` tag 与 GitHub Release 已创建；历史 tag 未移动、未删除、未重建。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；不执行真实外网 LLM。
- 发布后收口文档：`docs/post_release_check_v3.5.0.md`。

## v3.6.0 release prep（当前）

- 规划文档：`docs/v3_6_enterprise_identity_tenant_boundary_plan.md`。
- v3.6 定位：Enterprise Identity & Tenant Boundary。
- 当前已进入 release prep，版本已同步为 `3.6.0`。
- release prep 阶段约束：不打 tag，不创建 Release，不移动历史 tag。
- `v3.5.0` GitHub Release 已创建，`v3.5.0/v3.4.0/v3.3.0/v3.2.0/v3.1.0/v3.0.0` tags 保持不变。
- 现有 OIDC 仍为最小配置预检，不执行真实 token exchange，不宣称生产级 SSO/OIDC 完成。
- 当前尚未实现 tenant/org/project/resource ownership 运行时 enforcement，不宣称多租户完成。
- 保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，默认不连接真实外部 IdP，不输出真实 secret 原文。
- Phase 16.1~16.6 已完成；建议下一阶段：v3.6.0 tag 前最终复核。

## v3.6 Phase 16.1 身份与租户边界盘点（已完成）

- 新增 runbook：`docs/identity_tenant_boundary_inventory_v36.md`。
- 新增只读盘点脚本：`scripts/identity_tenant_boundary_inventory.py`，默认输出 `docs/reports/identity_tenant_boundary/`。
- 新增测试：`tests/test_identity_tenant_boundary_inventory_v361.py`。
- 盘点覆盖 `User`、`TokenPayload`、`UserRole`、JWT、`ROLE_HIERARCHY`、`ENDPOINT_PERMISSIONS`、OIDC 配置预检、审计文件和资源归属概念。
- 当前盘点结果预期为 `partial`：用户/JWT 尚无 tenant/org/project scope，尚无 tenant ownership 统一模型和运行时 enforcement，审计尚未定义 tenant scope。
- 保持只读边界：不读取 `.env` 或真实 secret 值，不连接真实 IdP，不执行 OIDC token exchange，不改 JWT payload，不新增 tenant enforcement，不写业务数据。
- 不宣称生产级 SSO/OIDC 或多租户完成。

## v3.6 Phase 16.2 租户归属模型草案（已完成）

- 新增模型设计文档：`docs/tenant_ownership_model_v36.md`。
- 新增 Pydantic 草案模型：`OrganizationScopeDraft`、`TenantScopeDraft`、`ProjectScopeDraft`、`PrincipalScopeDraft`、`RoleAssignmentDraft`、`ResourceScopeDraft`、`AuditScopeDraft`、`TenantOwnershipModelDraft`。
- 新增测试：`tests/test_tenant_ownership_model_v362.py`。
- 已明确 `organization`、`tenant`、`project`、`principal`、`role_assignment`、`resource_scope`、`audit_scope` 概念边界。
- 已明确未来可进入 JWT 的 claim 草案：`organization_id`、`tenant_id`、`project_id`；当前不改 `TokenPayload`。
- 已明确服务端 store 字段、审计字段、跨租户拒绝规则和迁移兼容策略。
- 本阶段不迁移数据库、不改 user store、不改 JWT payload、不启用 tenant enforcement、不改变默认离线 demo。
- 不宣称生产级 SSO/OIDC 或多租户完成。

## v3.6 Phase 16.3 RBAC 权限矩阵强化（已完成）

- 新增 runbook：`docs/rbac_permission_matrix_v36.md`。
- 新增只读矩阵导出脚本：`scripts/rbac_permission_matrix.py`，默认输出 `docs/reports/rbac_permission_matrix/`。
- 新增测试：`tests/test_rbac_permission_matrix_v363.py`。
- 矩阵覆盖 admin/operator/viewer/auditor 对 tasks、approvals、audit、metrics、tools、eval、memory、reflection、snapshot 的权限边界。
- 输出包含 role hierarchy、allowed roles、denied roles、401/403 拒绝证据、权限申请和定期复核流程。
- 保持只读边界：不新增生产登录系统，不绕过 `require_permission`，不改变默认 API token 要求，不默认启用 `AUTH_ENABLED` 或 `RBAC_ENABLED`。
- 不宣称权限治理已生产完成，不宣称生产级 SSO/OIDC 或多租户完成。

## v3.6 Phase 16.4 OIDC 生命周期演练计划（已完成）

- 新增 runbook：`docs/oidc_lifecycle_drill_v36.md`。
- 新增只读演练计划脚本：`scripts/oidc_lifecycle_drill.py`，默认输出 `docs/reports/oidc_lifecycle_drill/`。
- 新增测试：`tests/test_oidc_lifecycle_drill_v364.py`。
- 演练计划覆盖 OIDC 配置预检、token 生命周期、登出与会话失效、JWKS 轮换、client_secret 轮换和失败路径。
- 缺少真实 IdP opt-in 条件时记录为 `skipped`，不得伪造成 success。
- 所有 secret 只输出 env name 与 present 布尔状态。
- 本阶段默认不连接真实 IdP，不执行 OIDC token exchange，不修改 `.env`，不默认启用 `AUTH_ENABLED`、`RBAC_ENABLED`、`OIDC_ENABLED`。
- 不宣称生产级 SSO/OIDC 或多租户完成。

## v3.6 Phase 16.5 跨租户审计与拒绝证据（已完成）

- 新增 runbook：`docs/cross_tenant_audit_evidence_v36.md`。
- 新增只读证据模板脚本：`scripts/cross_tenant_audit_evidence.py`，默认输出 `docs/reports/cross_tenant_audit_evidence/`。
- 新增测试：`tests/test_cross_tenant_audit_evidence_v365.py`。
- 证据模板覆盖 allow、deny、audit record、export redaction、reviewer/owner evidence。
- 明确未来 audit event 必需 scope 字段：`organization_id`、`tenant_id`、`project_id`、`resource_id`、`actor_principal_id`、`decision`、`denial_reason`。
- 支持引用 RBAC matrix、tenant model 文档和 audit export sample，仅消费元数据；发现 prompt/secret/token/连接串密码原文时输出 `blocked`，且不泄露原文。
- 本阶段不修改 audit store schema，不生成伪造的跨租户通过证据，不启用 tenant enforcement，不改 JWT payload。
- 不宣称生产级 SSO/OIDC 或多租户完成。

## v3.6 Phase 16.6 release prep（已完成）

- 已同步版本到 `3.6.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、脚本 version markers、相关测试断言。
- 已新增 `RELEASE_NOTES_v3.6.0.md`。
- 已新增 `docs/release_review_v3.6_enterprise_identity_tenant_boundary.md`。
- Phase 16.1~16.5 纳入 v3.6.0 release prep 范围。
- 前端移除构建期 Google Fonts 依赖，默认离线 build 可通过。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；不执行真实外网 LLM。
- 不宣称公网生产可直接上线，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 或多租户完成。

## v3.7 路线规划已开启（当前）

- 规划文档：`docs/v3_7_external_integration_real_provider_acceptance_plan.md`。
- v3.7 定位：External Integration & Real Provider Acceptance。
- 当前先进入规划与只读基线阶段，版本保持 `3.6.0`。
- 本轮不打 tag、不创建 GitHub Release、不移动历史 tag。
- 由于当前环境 GitHub HTTPS 推送不可用，`v3.6.0` release prep 提交已在本地完成，远端同步需网络恢复后执行。
- Phase 17.1~17.5 与 v3.7.0 release prep 已完成；tag/Release 待用户单独确认。

## v3.7 Phase 17.1 外部集成与真实 provider 基线盘点（已完成）

- 新增 runbook：`docs/external_provider_acceptance_inventory_v37.md`。
- 新增只读盘点脚本：`scripts/external_provider_acceptance_inventory.py`，默认输出 `docs/reports/external_provider_acceptance_inventory/`。
- 新增测试：`tests/test_external_provider_acceptance_inventory_v371.py`。
- 盘点覆盖 external MCP、real LLM provider、LLM judge、PostgreSQL、Redis、deployment guard、tool approval audit、frontend offline build。
- 输出明确 `read_only=true`、`real_llm_executed=false`、`external_mcp_connected=false`、`business_system_connected=false`。
- 仅输出 env name、present 布尔状态和本地文件存在性，不读取或输出真实 secret 原文。
- 不宣称真实 provider、真实外部 MCP 或真实业务系统生产验收完成。

## v3.7 Phase 17.2 External MCP acceptance gate（已完成）

- 新增 runbook：`docs/external_mcp_acceptance_gate_v37.md`。
- 新增只读门禁脚本：`scripts/external_mcp_acceptance_gate.py`，默认输出 `docs/reports/external_mcp_acceptance_gate/`。
- 新增测试：`tests/test_external_mcp_acceptance_gate_v372.py`。
- 门禁覆盖 real mode opt-in、command configured、command allowlist、tool allowlist、timeout config、lifecycle hardening、approval/audit boundary、fake fixture coverage。
- 输出明确 `external_mcp_connected=false`、`mcp_process_started=false`、`mcp_tools_list_executed=false`、`mcp_tools_call_executed=false`。
- 本阶段不启动 MCP subprocess，不执行真实 `tools/list` 或 `tools/call`，不宣称真实外部 MCP 生产验收完成。

## v3.7 Phase 17.3 Real LLM provider acceptance gate（已完成）

- 新增 runbook：`docs/real_llm_provider_acceptance_gate_v37.md`。
- 新增只读门禁脚本：`scripts/real_llm_provider_acceptance_gate.py`，默认输出 `docs/reports/real_llm_provider_acceptance_gate/`。
- 新增测试：`tests/test_real_llm_provider_acceptance_gate_v373.py`。
- 门禁覆盖 preflight config、network check gate、smoke opt-in、budget/cache/fallback、PII/prompt guardrails、report redaction、judge acceptance、evidence index。
- 输出明确 `real_llm_executed=false`、`provider_network_check_executed=false`、`pilot_report_content_read=false`。
- 可选索引 pilot report 目录时仅读取文件元数据，不读取报告正文。
- 本阶段不调用真实外网 LLM，不执行 provider network check，不宣称真实 LLM 生产验收完成。
## v3.8 Phase 18.1 SRE observability baseline（当前已完成）

- 新增 runbook：`docs/sre_observability_baseline_v38.md`。
- 新增只读脚本：`scripts/sre_observability_baseline.py`，默认输出 `docs/reports/sre_observability_baseline/`。
- 新增测试：`tests/test_sre_observability_baseline_v381.py`。
- 基线覆盖 runtime metrics/cost API、runtime snapshot、operations summary、audit export、structured logging、failure diagnostics、backup/restore runbook、APM/告警/容量/备份/DR 缺口。
- 默认 fake/offline，不启动服务，不访问在线端点，不连接真实 APM、日志平台、告警平台或值班系统。
- 默认不执行真实压测、备份恢复或灾备切换；缺少 opt-in 条件时输出 `skipped`，不伪造成成功。
- 该阶段不代表企业级 SRE、RTO/RPO、SLO/SLI、告警触发或生产 DR 验收已完成。
## v3.8 Phase 18.2 SLO/SLI and alerting runbook pack（当前已完成）

- 新增 runbook：`docs/slo_alerting_runbook_pack_v38.md`。
- 新增只读脚本：`scripts/slo_alerting_runbook_pack.py`，默认输出 `docs/reports/slo_alerting_runbook/`。
- 新增测试：`tests/test_slo_alerting_runbook_pack_v382.py`。
- 覆盖 SLO/SLI 指标来源、SLO 目标配置、structured logging 告警上下文、告警分级与路由、on-call 升级、alert dry-run 证据和 incident runbook 串联。
- 默认 fake/offline，不启动服务，不访问在线端点，不连接真实告警平台，不发送真实告警，不通知真实 on-call，不调用真实 webhook。
- 缺少 opt-in 或演练证据时输出 `skipped`，不伪造成成功；该阶段不代表企业级 SLO/告警生产验收完成。
## v3.8 Phase 18.3 Backup/restore and DR drill evidence pack（当前已完成）

- 新增 runbook：`docs/backup_restore_dr_evidence_pack_v38.md`。
- 新增只读脚本：`scripts/backup_restore_dr_evidence_pack.py`，默认输出 `docs/reports/backup_restore_dr_evidence/`。
- 新增测试：`tests/test_backup_restore_dr_evidence_pack_v383.py`。
- 覆盖备份范围、部署与迁移边界、RTO/RPO 配置、备份演练证据、恢复 dry-run 证据、DR failover 证据和 runbook 串联。
- 默认 fake/offline，不启动服务，不连接真实 PostgreSQL/Redis/对象存储，不执行真实备份、恢复、灾备切换或 Alembic migration。
- 缺少 opt-in 或演练证据时输出 `skipped`，不伪造成成功；该阶段不代表 RTO/RPO 或生产 DR 验收完成。
## v3.8 Phase 18.4 Capacity and load-test readiness plan（当前已完成）

- 新增 runbook：`docs/capacity_load_test_readiness_plan_v38.md`。
- 新增只读脚本：`scripts/capacity_load_test_readiness_plan.py`，默认输出 `docs/reports/capacity_load_test_readiness/`。
- 新增测试：`tests/test_capacity_load_test_readiness_plan_v384.py`。
- 覆盖关键 API 入口、流量模型目标、request guard、容量测试可观测性、load-test dry-run 证据、soak test 证据和 runbook 串联。
- 默认 fake/offline，不启动服务，不访问在线端点，不执行真实压测、soak test、并发请求或容量探测。
- 缺少 opt-in 或报告证据时输出 `skipped`，不伪造成成功；该阶段不代表生产容量上限验收完成。
## v3.8.0 release prep（当前已完成）

- 版本已同步到 `3.8.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、v3.8 脚本 version markers、相关测试断言。
- 已新增 `RELEASE_NOTES_v3.8.0.md`。
- 已新增 `docs/release_review_v3.8_sre_observability_dr.md`。
- Phase 18.1~18.4 纳入 v3.8.0 release prep 范围。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；默认不连接真实 APM、日志、告警、对象存储、PostgreSQL、Redis、IdP、外部 MCP 或业务系统。
- 不宣称公网生产可直接上线，不宣称企业级 SRE、RTO/RPO、DR、容量上限、真实 LLM 生产验收、生产级 SSO/OIDC 或多租户完成。
## v3.9 Compliance Security Hardening 路线规划（当前）

- 规划文档：`docs/v3_9_compliance_security_hardening_plan.md`。
- v3.9 定位：Compliance Security Hardening。
- 当前已进入 v3.9.0 release prep，版本已同步到 `3.9.0`。
- 本轮不打 tag，不创建 GitHub Release，不移动历史 tag。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM，不连接真实外部系统，不执行真实安全扫描、密钥轮换、权限变更、审计导出、发布或回滚。
- 不宣称公网生产可直接上线，不宣称企业级合规、安全治理、发布门禁或密钥治理完成。

## v3.9 Phase 19.1 Compliance security baseline inventory（当前已完成）

- 新增 runbook：`docs/compliance_security_baseline_v39.md`。
- 新增只读脚本：`scripts/compliance_security_baseline.py`，默认输出 `docs/reports/compliance_security_baseline/`。
- 新增测试：`tests/test_compliance_security_baseline_v391.py`。
- 覆盖 deployment guard、安全响应头、request guard、结构化日志脱敏、审计留存与导出、RBAC、OIDC、prompt injection、PII guard、跨租户审计和 release review 证据缺口。
- 默认不启动服务，不访问在线端点，不连接真实外部系统，不执行真实安全扫描、审计导出、密钥轮换、权限变更、发布或回滚。
- 缺少正式签核或演练证据时输出 `skipped`，不伪造成成功；该阶段不代表企业级合规安全验收完成。
## v3.9 Phase 19.2 Secret rotation and leakage response pack（当前已完成）

- 新增 runbook：`docs/secret_rotation_leakage_response_pack_v39.md`。
- 新增只读脚本：`scripts/secret_rotation_leakage_response_pack.py`，默认输出 `docs/reports/secret_rotation_leakage_response/`。
- 新增测试：`tests/test_secret_rotation_leakage_response_pack_v392.py`。
- 覆盖 JWT/OIDC/数据库/Redis/LLM/MCP/业务系统/告警 webhook 等 secret surface、脱敏审计边界、身份密钥生命周期、外部集成密钥边界、治理例外串联、轮换/泄漏响应/撤销恢复演练证据缺口。
- 默认不读取 `.env` 或真实 secret 值，不连接真实密钥系统，不执行真实密钥创建、轮换、撤销、禁用、泄漏扫描或告警通知。
- 缺少演练证据时输出 `skipped`，不伪造成成功；该阶段不代表企业级密钥治理完成。
## v3.9 Phase 19.3 Release gate and rollback governance pack（当前已完成）

- 新增 runbook：`docs/release_gate_rollback_governance_pack_v39.md`。
- 新增只读脚本：`scripts/release_gate_rollback_governance_pack.py`，默认输出 `docs/reports/release_gate_rollback_governance/`。
- 新增测试：`tests/test_release_gate_rollback_governance_pack_v393.py`。
- 覆盖 deployment guard、compose、Alembic、release notes、release review、变更审批、发布签核、回滚演练、治理例外和安全合规串联证据缺口。
- 默认不启动服务，不访问在线端点，不执行 git tag、GitHub Release、部署、迁移、回滚、数据恢复或外部系统调用。
- 缺少变更审批、发布签核或回滚演练证据时输出 `skipped`，不伪造成成功；该阶段不代表生产发布门禁或回滚验收完成。
## v3.9 Phase 19.4 Security regression and compliance evidence pack（当前已完成）

- 新增 runbook：`docs/security_regression_compliance_evidence_pack_v39.md`。
- 新增只读脚本：`scripts/security_regression_compliance_evidence_pack.py`，默认输出 `docs/reports/security_regression_compliance_evidence/`。
- 新增测试：`tests/test_security_regression_compliance_evidence_pack_v394.py`。
- 覆盖 prompt injection、PII 泄漏、SQL guard、边界防护、身份/RBAC、跨租户拒绝、审计导出脱敏、发布门禁和合规证据串联缺口。
- 默认不启动服务，不访问在线端点，不执行真实 SAST、DAST、依赖扫描、红队测试、外部审计或外部系统调用。
- 缺少外部安全扫描、正式安全签核或合规证据复核时输出 `skipped`，不伪造成成功；该阶段不代表企业级安全合规验收完成。
## v3.9.0 release prep（当前已完成）

- 版本已同步到 `3.9.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、v3.9 脚本 version markers、相关测试断言。
- 已新增 `RELEASE_NOTES_v3.9.0.md`。
- 已新增 `docs/release_review_v3.9_compliance_security_hardening.md`。
- Phase 19.1~19.4 纳入 v3.9.0 release prep 范围。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；默认不连接真实外部系统。
- 不宣称公网生产可直接上线，不宣称企业级合规、安全治理、密钥治理、发布门禁、回滚验收、真实 LLM 生产验收、生产级 SSO/OIDC 或多租户完成。
## v4.0 Phase 20.1 Production launch readiness evidence review pack（当前已完成）

- 新增规划文档：`docs/v4_0_production_launch_readiness_plan.md`。
- 新增 runbook：`docs/production_launch_readiness_review_v40.md`。
- 新增只读脚本：`scripts/production_launch_readiness_review.py`，默认输出 `docs/reports/production_launch_readiness/`。
- 新增测试：`tests/test_production_launch_readiness_review_v401.py`。
- 覆盖 v3.5~v3.9 试点收口、证据归档、真实 provider 验收、SRE/DR、容量、安全合规、发布门禁和回滚治理证据入口。
- 默认输出 `partial` + `Manual-Review`，公网生产直上保持 `No-Go`；缺少真实生产验收证据时不伪造成 `success`。
- 已收紧上游 `blocked/failed`、输入不足 `skipped`、secret-like JSON 键值脱敏和 blocked 状态下 `controlled_internal_pilot=No-Go` 语义。
- 已根据子 agent 审查补强 `external_system_connected` 边界违规识别。
- 验证通过：v4.0 Phase 20.1 单测 7 passed；v4.0 + v3.9 关联测试随 Phase 20.2 更新为 34 passed, 1 warning；`git diff --check` 仅 CRLF 提示。
- 默认 fake/offline，不启动服务，不访问在线端点，不连接真实外部系统，不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、审计导出、密钥轮换或权限变更。
- 本阶段不改版本号，不打 tag，不创建 GitHub Release，不宣称生产上线批准完成。
## v4.0 Phase 20.2 Launch blocker register（当前已完成）

- 新增 runbook：`docs/launch_blocker_register_v40.md`。
- 新增只读脚本：`scripts/launch_blocker_register.py`，默认输出 `docs/reports/launch_blockers/`。
- 新增测试：`tests/test_launch_blocker_register_v402.py`。
- 将 Phase 20.1 的 production blockers 和 missing conditions 整理为 blocker register，字段覆盖 blocker id、来源、风险描述、影响范围、责任人、到期时间、补偿控制、关闭证据、状态、审批状态和下一步动作。
- 默认无上游输入或上游 `skipped` 时输出 `skipped`；存在待关闭 blocker 时输出 `partial`；上游 `blocked/failed`、secret-like 输入、自动批准/关闭标记或边界违规时输出 `blocked`。
- `auto_approved=false`、`auto_closed=false`，不自动批准上线，不自动关闭阻断项，不宣称生产 Go。
- 已根据子 agent 审查补强上游 `skipped` 保留、`auto_approved/auto_closed` 阻断和 success 语义文档。
- 验证通过：v4.0 Phase 20.1/20.2 + v3.9 关键安全合规关联测试 34 passed, 1 warning；`git diff --check` 仅 CRLF 提示。
- 默认 fake/offline，不启动服务，不访问在线端点，不连接真实外部系统，不执行真实生产操作。
## v4.0 Phase 20.3 Production runbook finalization（当前已完成）

- 新增 runbook：`docs/production_runbook_finalization_v40.md`。
- 新增只读脚本：`scripts/production_runbook_finalization.py`，默认输出 `docs/reports/production_runbook_finalization/`。
- 新增测试：`tests/test_production_runbook_finalization_v403.py`。
- 汇总部署、回滚、incident、DR、密钥轮换、审计导出、SLO/告警、容量、Launch Readiness 和 blocker register 的本地 runbook 入口。
- 默认仅检查本地文件存在性和可选上游 JSON 结构化字段，不读取 Markdown 报告正文，不执行真实生产操作。
- 输出明确 `deployment_executed=false`、`rollback_executed=false`、`alert_sent=false`、`oncall_notified=false`、`auto_approved=false`、`auto_closed=false`。
- 默认不把 runbook 入口存在性伪造成生产 Go。
- 已根据子 agent 审查补强：缺少上游 Phase 20.1/20.2 JSON 时输出 `skipped`，透传 blocker 计数与上游 Go/No-Go，audit log/export 验证入口纳入必需项。
- 验证通过：v4.0 Phase 20.1/20.2/20.3 + v3.9 关键安全合规关联测试 39 passed；`git diff --check` 仅 CRLF 提示。

## v4.1 Phase 21.1 Launch blocker closure workflow（当前已完成）

- 新增规划文档：`docs/v4_1_evidence_execution_closure_plan.md`。
- 新增 runbook：`docs/launch_blocker_closure_workflow_v41.md`。
- 新增只读脚本：`scripts/launch_blocker_closure_workflow.py`，默认输出 `docs/reports/launch_blocker_closure/`。
- 新增测试：`tests/test_launch_blocker_closure_workflow_v411.py`。
- 该工作流消费 v4.0 Launch Blocker Register JSON 与可选脱敏 closure evidence JSON，仅判断 blocker 是否具备进入人工复核的 owner、due_at、补偿控制、证据引用、reviewer 与审批状态。
- 所有证据齐全时整体仍输出 `partial` + `Manual-Review`，不输出生产 Go，不自动关闭 blocker，不伪造人工审批。
- 保持 `auto_approved=false`、`auto_closed=false`、`production_direct_launch=No-Go`。
- 保持只读边界：不读取 Markdown 正文，不修改上游报告或 `.env`，不连接真实 LLM/MCP/IdP/业务系统/数据库/Redis/APM/日志/告警/KMS/Vault/云平台，不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、审计导出、密钥轮换或权限变更。
- 验证通过：`pytest tests/test_launch_blocker_closure_workflow_v411.py` 为 8 passed。

## v4.1 Phase 21.2 Closure evidence index（当前已完成）

- 新增 runbook：`docs/closure_evidence_index_v41.md`。
- 新增只读脚本：`scripts/closure_evidence_index.py`，默认输入 `docs/reports/launch_blocker_closure/`，默认输出 `docs/reports/closure_evidence_index/`。
- 新增测试：`tests/test_closure_evidence_index_v412.py`。
- 该索引只读取 closure workflow JSON 的结构化元数据，汇总 report count、latest report、closure item totals 与状态分布。
- 不读取 Markdown 报告正文，不展开证据报告内容，不修改、不移动、不删除输入证据，不自动执行 retention 清理。
- 检测到 secret-like 输入、非只读报告、自动审批/自动关闭标记或上游 blocked/failed 时输出 `blocked`。
- 输出仍保持 `production_direct_launch=No-Go`、`auto_approved=false`、`auto_closed=false`，不宣称 blocker 已关闭或生产发布批准完成。
- 验证通过：`pytest tests/test_closure_evidence_index_v412.py` 为 5 passed。

## v4.1 Phase 21.3 Manual signoff package（当前已完成）

- 新增 runbook：`docs/manual_signoff_package_v41.md`。
- 新增只读脚本：`scripts/manual_signoff_package.py`，默认输出 `docs/reports/manual_signoff_package/`。
- 新增测试：`tests/test_manual_signoff_package_v413.py`。
- 该签核包消费 Closure Evidence Index JSON，生成 release manager、security reviewer、business owner、operations owner 所需的人工复核项。
- 签核包生成完成时仍输出 `partial` + `Manual-Review`，`manual_signoff_completed=false`，`auto_signed=false`。
- 检测到上游 blocked/failed、secret-like 输入、非只读报告、自动审批/自动关闭标记或 release/tag 标记时输出 `blocked`。
- 保持 `production_direct_launch=No-Go`、`auto_approved=false`、`auto_closed=false`，不宣称生产发布批准完成。
- 验证通过：`pytest tests/test_manual_signoff_package_v413.py` 为 5 passed。

## v4.2 Phase 22.1 Controlled production acceptance drill（当前已完成）

- 新增规划文档：`docs/v4_2_controlled_production_acceptance_plan.md`。
- 新增 runbook：`docs/controlled_production_acceptance_drill_v42.md`。
- 新增只读脚本：`scripts/controlled_production_acceptance_drill.py`，默认输出 `docs/reports/controlled_production_acceptance/`。
- 新增测试：`tests/test_controlled_production_acceptance_drill_v421.py`。
- 覆盖 real LLM、OIDC/SSO、external MCP、PostgreSQL、Redis、业务系统、APM/logging/alerting、backup/restore/DR、capacity/load/soak、security/compliance、release/rollback gate。
- 该演练包只消费脱敏 acceptance evidence JSON，不连接真实外部系统，不执行真实验收动作。
- 缺少验收证据或上游 skipped 时输出 `skipped`；证据可进入人工复核时输出 `partial` + `Manual-Review`；检测到 secret-like、真实执行/连接、release/tag、自动审批/自动关闭标记时输出 `blocked`。
- 输出明确 `real_llm_executed=false`、`external_mcp_connected=false`、`database_connected=false`、`redis_connected=false`、`business_system_connected=false`、`auto_approved=false`、`auto_closed=false`、`production_direct_launch=No-Go`。
- 当前仍不宣称真实生产验收完成。
- 验证通过：`pytest tests/test_controlled_production_acceptance_drill_v421.py` 为 6 passed。

## v4.2 Phase 22.2 Acceptance drill evidence index（当前已完成）

- 新增 runbook：`docs/acceptance_drill_evidence_index_v42.md`。
- 新增只读脚本：`scripts/acceptance_drill_evidence_index.py`，默认输入 `docs/reports/controlled_production_acceptance/`，默认输出 `docs/reports/acceptance_drill_index/`。
- 新增测试：`tests/test_acceptance_drill_evidence_index_v422.py`。
- 仅扫描受控生产验收演练 JSON 报告，不读取 Markdown 报告正文，不展开证据报告内容。
- 检测到 secret-like 输入、非只读报告、真实执行/连接标记、release/tag、自动审批/自动关闭标记或上游 blocked/failed 时输出 `blocked`。
- 输出仍保持 `production_direct_launch=No-Go`、`auto_approved=false`、`auto_closed=false`，不宣称真实生产验收完成。
- 验证通过：`pytest tests/test_acceptance_drill_evidence_index_v422.py` 为 5 passed。

## v4.2 Phase 22.3 Production acceptance gap register（当前已完成）

- 新增 runbook：`docs/production_acceptance_gap_register_v42.md`。
- 新增只读脚本：`scripts/production_acceptance_gap_register.py`，默认输出 `docs/reports/production_acceptance_gaps/`。
- 新增测试：`tests/test_production_acceptance_gap_register_v423.py`。
- 该登记册消费 Acceptance Drill Evidence Index JSON，把 skipped/blocked 域整理为人工跟踪 gap，字段覆盖 gap id、来源、风险描述、影响范围、责任人、到期时间、补偿控制、关闭证据、状态、审批状态和下一步动作。
- 默认 gap 需要人工 owner、due_at、补偿控制和关闭证据，不自动关闭，不自动审批。
- 检测到上游 blocked/failed、secret-like 输入、非只读报告、真实执行/连接标记、release/tag、自动审批/自动关闭标记时输出 `blocked`。
- 输出仍保持 `production_direct_launch=No-Go`、`auto_approved=false`、`auto_closed=false`，不宣称真实生产验收完成。
- 验证通过：`pytest tests/test_production_acceptance_gap_register_v423.py` 为 6 passed。

## v4.3 Phase 23.1 Operations summary v4 evidence entry（当前已完成）

- 新增规划文档：`docs/v4_3_operational_governance_console_readiness_plan.md`。
- 增强 `/operations/summary` 的 `observability.v4_evidence` 元数据。
- 纳入 v4.1/v4.2 证据 runbook 与默认报告目录：launch blocker closure、closure evidence index、manual signoff package、controlled production acceptance、acceptance drill index、production acceptance gaps。
- 仅统计 JSON 报告数量，不读取报告正文，不连接真实外部系统，不执行真实 LLM，不自动审批，不自动关闭 blocker/gap。
- `last_known_report_counts` 新增 `v4_evidence_reports`。
- 验证通过：`pytest tests/test_operations_summary_v312.py` 为 2 passed, 1 warning。

## v4.3 Phase 23.2 Frontend v4 evidence read-only view（当前已完成）

- 增强前端 `/operations` 页面，展示 `observability.v4_evidence` 的模式、边界、总 JSON 报告数和各证据入口的 runbook/目录计数。
- 更新前端类型契约：`frontend/src/types/api.ts`。
- 更新前端只读页面：`frontend/src/app/operations/page.tsx`。
- 保持只读边界：不读取报告正文，不新增生成/删除/清理/审批/关闭 blocker 或 gap 的入口，不触发真实 LLM，不连接真实外部系统，不输出 secret 原文。

## v4.3 Phase 23.3 Operations governance empty/status semantics polish（当前已完成）

- 增强前端 `/operations` 的 v4 evidence 空态和状态语义展示。
- 新增 entry state：`directory_missing`、`no_json_reports`、`metadata_available`。
- 明确 `metadata_available` 仅表示目录中存在 JSON 元数据，不代表验收通过。
- 明确 `skipped`、`blocked`、`partial`、`success` 的运营含义；`partial/success` 仍不等于生产上线批准。
- 保持只读边界：不读取报告正文，不触发真实 LLM，不连接真实外部系统，不输出 secret 原文。

## v4.3.0 release prep（当前已完成）

- 版本已同步到 `4.3.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、相关测试断言。
- 已新增 `RELEASE_NOTES_v4.3.0.md`。
- 已新增 `docs/release_review_v4.3_operational_governance_console_readiness.md`。
- v4.0~v4.3 纳入 v4.3.0 release prep 范围：生产上线评审、阻断项登记、runbook finalization、关闭证据、人工签核、受控生产验收、验收缺口登记和运营治理台只读展示。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline；默认 pytest/CI 不调用真实 LLM；默认不连接真实外部系统。
- 不宣称公网生产可直接上线，不宣称真实 LLM/MCP/IdP/PostgreSQL/Redis/业务系统生产验收完成，不宣称生产级 SSO/OIDC、多租户、复杂 BI、企业级 SRE/DR/容量验收完成。

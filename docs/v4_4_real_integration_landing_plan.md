# v4.4 Real Integration Landing Plan

## 阶段定位

v4.4 面向真实 LLM、PostgreSQL、Redis 与真实 MCP Server 的受控接入落地。目标不是把默认路径切换为真实外部依赖，而是在现有 fake/offline 默认能力之上，建立可执行、可审查、可回滚的真实集成接入门禁。

当前结论：

- 企业内网受控试点可以继续推进。
- 真实 LLM、PostgreSQL、Redis、真实 MCP Server 只能通过显式 opt-in 进入验收。
- 默认 pytest/CI 不调用真实 LLM，不连接真实数据库、Redis 或 MCP Server。
- 不读取或输出 `DATABASE_URL`、`REDIS_URL`、LLM API key、`REAL_LLM_API_KEY_ENV` 指向值或 `MCP_SERVER_COMMAND` 中可能包含的 secret 原文。
- 当前不打 tag，不创建 GitHub Release，不移动历史 tag。
- 当前仍不宣称真实 LLM、PostgreSQL、Redis 或真实 MCP Server 生产验收完成。

## Phase 24.1 Real Integration Readiness Matrix

已落地：

- `scripts/real_integration_readiness_matrix.py`
- `tests/test_real_integration_readiness_matrix_v441.py`
- 默认输出目录：`docs/reports/real_integration_readiness/`

目标：

- 汇总真实 LLM、PostgreSQL、Redis、真实 MCP Server 的能力入口、配置入口、本地证据文件和缺口。
- 输出 JSON + Markdown 只读矩阵。
- 缺少 opt-in 条件时输出 `skipped` 或 `partial`，不得伪造成 `success`。
- 明确 `real_llm_executed=false`、`database_connected=false`、`redis_connected=false`、`external_mcp_connected=false`、`migration_executed=false`。

## Phase 24.2 MCP Tool Allowlist Runtime Guard

已落地：

- `Settings` 新增 `mcp_tool_allowlist`。
- `.env.example` 与 `.env.production.example` 新增 `MCP_TOOL_ALLOWLIST`。
- `ToolGateway` 在 MCP discovery 阶段过滤未列入 allowlist 的工具。
- `ToolGateway.call()` 对 MCP 工具调用做二次 allowlist 拦截。
- `app.main` 在 `MCP_MODE=real` 注册真实 MCP Server 时传入 tool allowlist。
- deployment guard 在 production + `MCP_MODE=real` 时要求 `MCP_SERVER_COMMAND_ALLOWLIST` 与 `MCP_TOOL_ALLOWLIST` 均非空。

边界：

- 默认 `MCP_MODE=fake` 不变。
- 未配置真实 MCP 时不启动 MCP subprocess。
- 工具级 allowlist 不替代 ToolGateway、PolicyEngine、审批链路或审计链路。
- 该改动只完成 runtime 安全边界补强，不代表真实 MCP Server 生产验收完成。

## Phase 24.3 Redis Rate Limit Backend

已落地：

- `Settings` 新增 `rate_limit_backend`，默认 `memory`。
- `.env.example` 与 `.env.production.example` 新增 `RATE_LIMIT_BACKEND=memory`。
- `RateLimitMiddleware` 根据 `RATE_LIMIT_BACKEND` 选择 memory 或 Redis backend。
- Redis backend 使用 Redis `INCR` + `EXPIRE` 维护固定窗口计数。
- Redis disabled、NoopRedisClient 或 Redis 异常时回落 memory backend。
- deployment guard 校验 `RATE_LIMIT_BACKEND` 只能为 `memory/redis`；当 `RATE_LIMIT_BACKEND=redis` 时要求 `REDIS_ENABLED=true` 与 `REDIS_URL` 非空。
- Redis 连接成功日志不输出 `REDIS_URL` 原文。

边界：

- 默认仍为 `RATE_LIMIT_BACKEND=memory`，不连接 Redis。
- Redis backend 的本地单测不等于真实 Redis 多实例限流生产验收。
- 多实例生产仍需要真实 Redis 或网关级限流 smoke、故障恢复、断连降级和观测证据。

## Phase 24.4 Env Profile and Smoke Plan

已落地：

- `scripts/real_integration_env_profile.py`
- `tests/test_real_integration_env_profile_v444.py`
- `docs/real_integration_env_profile_v44.md`
- `scripts/real_integration_smoke_plan.py`
- `tests/test_real_integration_smoke_plan_v443.py`
- `docs/real_integration_smoke_plan_v44.md`

覆盖域：

- `real_llm`
- `postgres`
- `redis`
- `external_mcp`
- `staging_smoke`

边界：

- 只解析 `.env.example` 与 `.env.production.example` 的键名、占位状态和当前进程环境变量 present 布尔。
- `REAL_LLM_API_KEY_ENV` 只检查目标环境变量是否存在，不读取目标值。
- 不提供真实执行参数，不连接真实 LLM/PostgreSQL/Redis/MCP。
- 模板 literal 值只输出状态，不输出原值；secret-like 文本触发 blocked 或 redacted。

## Phase 24.5 Combined Integration Staging Gate

已落地：

- `scripts/real_integration_staging_gate.py`
- `tests/test_real_integration_staging_gate_v442.py`
- `docs/real_integration_staging_gate_v44.md`
- 默认输出目录：`docs/reports/real_integration_staging_gate/`

该 gate 只消费七类 JSON 证据：

- `docs/reports/real_integration_env_profile/`
- `docs/reports/real_integration_smoke_plan/`
- `docs/reports/real_integration_staging_smoke/`
- `docs/reports/real_integration_readiness/`
- `docs/reports/real_llm_provider_acceptance_gate/`
- `docs/reports/external_mcp_acceptance_gate/`
- `docs/reports/store_redis_readiness_drill/`

规则：

- 缺证据或上游 skipped/failed 时保持 `skipped`。
- 发现 secret-like 内容、异常执行 flag 或上游 blocked 时触发 `blocked`。
- 七类证据全部脱敏且无 skipped/blocked 时，只进入 `partial` / `Manual-Review`。
- `public_production_direct_launch` 始终为 `No-Go`。

## Phase 24.6 Real Integration Gap Register

已落地：

- `scripts/real_integration_gap_register.py`
- `tests/test_real_integration_gap_register_v445.py`
- 默认输出目录：`docs/reports/real_integration_gap_register/`

该登记表只消费既有 JSON 证据，把 `skipped` 与缺失条件归并为以下执行缺口：

- `real_llm`
- `postgres`
- `redis`
- `external_mcp`
- `combined_gate`

每个缺口输出：

- owner
- next_action
- next_evidence
- source_evidence_ids

边界：

- 不连接真实 LLM、PostgreSQL、Redis 或 MCP Server。
- 不执行 Alembic migration。
- 不写业务/审计/指标数据。
- 不读取或输出 secret 原文。
- 只要仍存在 open gap，组合结论保持 `Needs-Input`，公网生产直上仍为 `No-Go`。

## Phase 24.7 Controlled Real Integration Staging Smoke

已落地：

- `scripts/real_integration_staging_smoke.py`
- `tests/test_real_integration_staging_smoke_v446.py`
- `docs/real_integration_staging_smoke_v44.md`
- 默认输出目录：`docs/reports/real_integration_staging_smoke/`

该脚本提供真实 LLM、PostgreSQL、Redis 与 external MCP 的统一 staging smoke 编排入口。默认只生成 dry-run 证据；只有命令行 `--execute`、`REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true` 和单域执行开关同时满足，并且单域 opt-in 条件完整时，才允许调用 smoke 执行器。

能力：

- 支持 `--domains real_llm`、`--domains postgres`、`--domains redis`、`--domains external_mcp` 分域执行。
- 默认执行器已接入 LLM preflight、database health、Redis health、MCP tools/list discovery。
- 输出只记录脱敏状态、数量、错误类型和执行标志。

边界：

- 默认不连接真实外部系统。
- 不执行 migration。
- 不写业务/审计/指标数据。
- 不输出 secret 原文。
- 真实执行结果只作为 staging 证据，不能自动宣称生产验收完成。

## 后续生产环境规划

下一阶段规划文档：

- `docs/v4_5_real_production_environment_landing_plan.md`

v4.5 将从“只读门禁 + 受控 staging smoke 入口”推进到真实生产使用环境落地规划，明确真实 LLM、PostgreSQL、Redis、external MCP 的生产配置、执行顺序、验收证据和 Go/No-Go。

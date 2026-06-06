# v4.5 真实生产环境落地计划

## 目标

v4.5 的目标是把 v4.4 已建立的只读门禁、gap register 和 staging smoke 入口，推进到企业内网生产试点或准生产环境的受控落地阶段。

本阶段必须纳入真实 LLM、真实 PostgreSQL、真实 Redis 与真实 MCP Server 的受控验证，同时保留默认 fake/offline 路径，默认 pytest/CI 不触发真实外部依赖。

本计划不宣称公网生产直上，不自动批准上线，不绕过人工 Go/No-Go。

## 当前基线

当前已具备：

- `real_integration_env_profile`：覆盖 `real_llm`、`postgres`、`redis`、`external_mcp`、`staging_smoke` 环境配置域。
- `real_integration_staging_smoke`：支持 `--execute` 与 `--domains`，可按域执行真实 LLM、PostgreSQL、Redis、external MCP 的受控 smoke。
- `real_integration_staging_gate`：消费结构化证据，输出组合门禁。
- `real_integration_gap_register`：消费多类证据，输出 open gap、owner、next_action、next_evidence。
- `.env.example` 与 `.env.production.example` 已包含 staging smoke 全局和单域执行开关。
- `frontend_production_build_check`、`production_runtime_smoke`、`production_auth_rbac_acceptance` 已形成本地生产可用性证据。

当前仍未完成：

- 未完成真实业务系统只读连接验收。
- 未完成真实 PostgreSQL/Redis/MCP 的完整生产验收闭环。
- Alembic migration 仍需人工批准窗口。
- 尚未形成完整生产试点人工签核包。

## 生产环境分层

### L0 默认开发环境

- `MCP_MODE=fake`
- `STORAGE_BACKEND=sqlite`
- `REDIS_ENABLED=false`
- `RATE_LIMIT_BACKEND=memory`
- `REAL_LLM_ACCEPTANCE_ENABLED=false`
- `REAL_INTEGRATION_STAGING_SMOKE_ENABLED=false`

用途：本地开发、默认 pytest、离线演示。不得连接真实外部系统。

### L1 受控 Staging 环境

必须具备：

- 通过外部 secret manager 注入 LLM key、`DATABASE_URL`、`REDIS_URL`、MCP 所需环境变量。
- `APP_ENV=staging` 或等价隔离标识。
- PostgreSQL、Redis、MCP Server 与业务网络隔离在受控内网。
- 可写数据仅限 staging 测试库，不使用生产业务数据。
- 所有 smoke 输出必须脱敏归档到 `docs/reports/` 或等价证据目录。

用途：真实连接 smoke、故障演练、回滚演练、组合 staging gate。

### L2 生产试点环境

必须具备：

- `APP_ENV=production`
- `AUTH_ENABLED=true`
- `RBAC_ENABLED=true`
- `STORAGE_BACKEND=postgres`
- `REDIS_ENABLED=true`
- `RATE_LIMIT_BACKEND=redis`
- 真实 LLM provider、预算、缓存、fallback、审计脱敏均启用。
- `MCP_MODE=real` 时必须配置 command allowlist、tool allowlist、env allowlist、timeout。
- deployment guard 必须通过。
- 仅允许人工批准后的有限用户、有限业务场景。

用途：企业内网生产试点。不得直接扩展为公网生产。

## Phase 25.1 真实环境配置冻结

目标：把真实生产试点所需配置从“可选键”提升为“受控配置清单”。

必须完成：

- 明确真实 LLM provider、model、base_url、API key env name。
- 明确 PostgreSQL 连接串来源、账号权限、schema、migration 策略。
- 明确 Redis 连接串来源、限流用途、缓存用途、断连降级策略。
- 明确 MCP Server command、args、workdir、env allowlist、command allowlist、tool allowlist。
- 明确审计、日志、指标、告警、备份恢复路径。

验收证据：

- 最新 `real_integration_env_profile` 模板键齐备，secret 不输出原文。
- `real_integration_gap_register` 中配置类 gap 已分配 owner。
- `.env.production.example` 只包含占位符，不包含真实 secret。

No-Go：

- secret 原文进入仓库、报告或日志。
- `MCP_MODE=real` 但缺少 command/tool allowlist。
- PostgreSQL/Redis 连接串使用弱口令或占位口令进入真实环境。

## Phase 25.2 真实 LLM 生产试点接入

目标：把真实 LLM 从 opt-in smoke 推进到受控生产试点可用。

配置要求：

- `REAL_LLM_ACCEPTANCE_ENABLED=true`
- `REAL_LLM_PREFLIGHT_ENABLED=true`
- `REAL_LLM_SMOKE_ENABLED=true`
- `REAL_LLM_PREFLIGHT_NETWORK_CHECK=true`
- `REAL_LLM_PROVIDER=litellm`
- `REAL_LLM_MODEL=<approved-model>`
- `REAL_LLM_API_KEY_ENV=<external-secret-env-name>`
- `REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true`
- `REAL_LLM_STAGING_SMOKE_EXECUTE=true`

执行顺序：

1. 运行 env profile，确认 key present，不读取 key value。
2. 运行只读 smoke plan，确认 opt-in 条件齐备。
3. 执行单域真实 LLM smoke：

```powershell
python scripts/real_integration_staging_smoke.py --execute --domains real_llm
```

4. 复核 `real_llm_executed=true`、`secret_plaintext_output=false`、错误数量、latency、provider/model 信息。
5. 运行组合 staging gate 和 gap register。
6. 人工审批后才允许进入有限生产试点流量。

No-Go：

- 无预算上限。
- 无 fallback。
- 输出 prompt 原文或 key 原文。
- 默认测试路径依赖真实 LLM。

## Phase 25.3 PostgreSQL 生产存储接入

目标：保留默认 SQLite 开发路径，同时让生产试点使用真实 PostgreSQL。

配置要求：

- `STORAGE_BACKEND=postgres`
- `DATABASE_URL=<external-secret-managed-url>`
- PostgreSQL 用户权限最小化。
- Alembic migration 只能在人工批准窗口执行。

执行顺序：

1. 运行 deployment guard。
2. 对 staging 数据库执行 migration precheck。
3. 在人工批准窗口执行 Alembic migration。
4. 执行单域 PostgreSQL smoke：

```powershell
python scripts/real_integration_staging_smoke.py --execute --domains postgres
```

也可以使用安全 PowerShell 入口，只把 `DATABASE_URL` 注入当前进程，结束后恢复环境：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\real_integration_infra_smoke.ps1 -Domains postgres
```

5. 验证 Task/User/Approval/Audit/Metrics/Graph checkpoint Store Factory 路径。
6. 验证 SQLite fallback 测试仍通过。

No-Go：

- 未经审批执行 migration。
- 默认开发路径被强制切到 PostgreSQL。
- 报告中出现 `DATABASE_URL` 原文。

## Phase 25.4 Redis 生产限流与缓存接入

目标：把 Redis 用于生产试点的限流、缓存和故障降级验证。

配置要求：

- `REDIS_ENABLED=true`
- `REDIS_URL=<external-secret-managed-url>`
- `RATE_LIMIT_BACKEND=redis`

执行顺序：

1. 运行 deployment guard。
2. 执行单域 Redis smoke：

```powershell
python scripts/real_integration_staging_smoke.py --execute --domains redis
```

也可以使用安全 PowerShell 入口，只把 `REDIS_URL` 注入当前进程，结束后恢复环境：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\real_integration_infra_smoke.ps1 -Domains redis
```

3. 验证 `RateLimitMiddleware` 使用 Redis backend。
4. 执行断连降级演练，确认回落 memory 或明确 blocked。
5. 执行多实例限流一致性验证。

No-Go：

- 使用 memory backend 宣称多实例生产限流完成。
- 报告中出现 `REDIS_URL` 原文。
- Redis 异常导致 500 或不可解释故障。

## Phase 25.5 真实 MCP Server 接入

目标：在 ToolGateway、PolicyEngine、审批链路和审计链路内接入真实 MCP Server。

配置要求：

- `MCP_MODE=real`
- `MCP_SERVER_COMMAND=<approved-command>`
- `MCP_SERVER_COMMAND_ALLOWLIST=<approved-command>`
- `MCP_TOOL_ALLOWLIST=<approved-tools>`
- `MCP_SERVER_ENV_ALLOWLIST=<approved-env-names>`
- `MCP_SERVER_TIMEOUT_SECONDS=<bounded-timeout>`
- `REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true`
- `MCP_STAGING_SMOKE_EXECUTE=true`

执行顺序：

1. 复核 command allowlist、tool allowlist、env allowlist。
2. 执行单域 MCP discovery smoke：

```powershell
python scripts/real_integration_staging_smoke.py --execute --domains external_mcp
```

也可以使用安全 PowerShell 入口传入已批准的 MCP command/tool allowlist 元数据；不要把 secret 放入 command 或 args：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\real_integration_infra_smoke.ps1 -Domains external_mcp -McpServerCommand "<approved-command>" -McpServerCommandAllowlist "<approved-command>" -McpToolAllowlist "<approved-tools>"
```

3. 只允许 allowlist 内工具进入 ToolGateway。
4. 对高风险工具执行审批恢复和审计验证。
5. 验证 subprocess timeout、stderr 截断、进程关闭、重启边界。

No-Go：

- MCP 工具绕过 ToolGateway、PolicyEngine、审批或审计。
- command/tool allowlist 为空。
- 输出 MCP command 中的 secret 参数。

## Phase 25.6 组合生产试点演练

目标：把真实 LLM、PostgreSQL、Redis、MCP 的单域证据组合成一次生产试点演练。

执行顺序：

1. 依次刷新：

```powershell
python scripts/real_integration_env_profile.py
python scripts/real_integration_smoke_plan.py
python scripts/real_integration_readiness_matrix.py
python scripts/real_integration_staging_smoke.py
python scripts/real_integration_staging_gate.py
python scripts/real_integration_gap_register.py
```

2. 单域 smoke 分批通过后，再执行组合 smoke：

```powershell
python scripts/real_integration_staging_smoke.py --execute --domains real_llm,postgres,redis,external_mcp
```

3. 重新生成 staging gate 和 gap register。
4. 人工 Go/No-Go 评审。
5. 生成生产试点证据包。

Go 条件：

- 证据齐全。
- gap register 无 P0/P1 open gap。
- `secret_plaintext_output=false`。
- 真实 LLM、PostgreSQL、Redis、MCP 单域 smoke 均有脱敏证据。
- deployment guard 通过。
- 回滚、备份恢复、告警、审计导出均有证据。

No-Go 条件：

- 任一真实域仍无证据。
- 任一报告出现 secret-like 原文。
- migration、真实工具调用或真实 LLM 调用绕过人工批准。
- 默认 fake/offline 路径被破坏。
- `public_production_direct_launch` 被改成 Go。

## Phase 25.7 发布与运行策略

生产试点发布前必须完成：

- 发布窗口和回滚窗口确认。
- 数据库备份和恢复演练完成。
- Redis 限流和缓存故障演练完成。
- LLM budget/fallback 告警阈值确认。
- MCP 工具 allowlist 和审批策略确认。
- 审计导出脱敏复核完成。

发布后 24 小时内必须观察：

- LLM 请求成功率、latency、fallback 率、token/cost。
- PostgreSQL 连接池、慢查询、migration 后错误。
- Redis 命中率、限流命中、断连恢复。
- MCP tools/list、tools/call 错误率、timeout、审批恢复。
- `/health`、`/operations/summary`、audit export、runtime metrics。

## 当前下一步

当前最优先不是直接宣称生产完成，而是继续补齐 L1 受控 staging 和 L2 生产试点证据：

1. 真实业务系统只读 smoke。
2. PostgreSQL 单域 smoke 与 migration precheck。
3. Redis 单域 smoke 与断连降级。
4. external MCP discovery smoke。
5. 组合 staging smoke。
6. staging gate + gap register 归零或形成明确人工签核。

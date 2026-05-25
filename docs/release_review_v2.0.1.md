# Project B v2.0.1 Release Review

## Release 口径

- 正式版本号：`v2.0.1`
- 当前测试口径：`513 passed` / `513+ tests`
- 本次 release 覆盖 Phase 1 Foundation、Phase 1.1 Integration Cleanup、Phase 1.1.1 Docker Startup & Release Polish。
- Phase 1.1 / Phase 1.1.1 是内部阶段名，不作为正式 release 版本号。

## Phase 1 Foundation 完成项

- SQLAlchemy / Alembic / psycopg 基座。
- PostgreSQL Store：Task / Approval / Audit / Metrics。
- Redis / NoopRedisClient 基座。
- JWT Auth：`/auth/login`、`/auth/me`。
- RBAC 依赖层：admin / operator / viewer / auditor。
- Store Factory：sqlite / postgres 切换能力。
- Docker Compose：postgres / redis / app。
- 默认兼容：`auth_enabled=false`、`rbac_enabled=false`、`storage_backend=sqlite`。

## Phase 1.1 Integration Cleanup 完成项

- `app.main` 主链路 getter 接入 Store Factory。
- `_build_runtime()` 复用主链路 store getter，不再绕回硬编码 SQLite。
- 关键 API 接入 RBAC：tasks、approvals、approval resume、audit、tools call、metrics。
- Docker app 启动改为 `scripts/start_app.py`：先初始化 demo DB，再按 postgres 配置执行 `alembic upgrade head`，最后启动 uvicorn。
- JWT 默认开发 secret 加固到 32+ 字符，不引入真实 secret。
- 文档同步 Phase 1 / Phase 1.1 口径。

## Phase 1.1.1 Docker Startup & Release Polish 完成项

- Dockerfile 已复制 `alembic.ini`。
- Dockerfile 已复制 `alembic/`。
- `scripts/start_app.py` 在容器内可找到 Alembic 配置和 migration 文件。
- `GET /tools` 接入 `tools:read`，viewer 可以读取工具列表；无 token 且 auth_enabled=true 时返回 401。
- README / AGENTS / enterprise pilot plan 统一正式版本号为 `v2.0.1`。
- 当前测试数量口径统一为 `513+`。

## 验证结果

- `python -m pytest tests/test_storage_v20.py tests/test_auth_v20.py tests/test_rbac_v20.py tests/test_config_v20.py -q`：`81 passed`
- `python -m pytest -q`：`513 passed`
- `docker compose config`：passed
- `docker compose build app`：passed

## 已知边界

- `auth_enabled=false` / `rbac_enabled=false` 是兼容默认值。
- `storage_backend=sqlite` 是默认值，SQLite fallback 保留。
- PostgreSQL / Redis 需要企业试点配置启用。
- InMemoryUserStore 不是生产用户存储。
- 尚未实现 LangGraph checkpoint / interrupt / resume。
- 尚未接真实 MCP stdio。
- 尚未接真实 LLM-as-Judge。
- 尚未做前端审批 UI。

## Phase 2 状态

可以进入 v2.0 Phase 2 Planning，但本 release 未实现 Phase 2。

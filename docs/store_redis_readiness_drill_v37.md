# v3.7 Store and Redis production readiness drill（只读）

Phase 17.4 建立 PostgreSQL Store 与 Redis 的生产准备演练证据，用于在真实数据库、Redis 和多实例限流验收前，确认本地工程基础、配置 opt-in、迁移预检、fallback、deployment guard、审计与指标存储边界是否清晰。

## 交付物

- 只读脚本：`scripts/store_redis_readiness_drill.py`
- 测试：`tests/test_store_redis_readiness_drill_v374.py`
- 默认输出目录：`docs/reports/store_redis_readiness_drill/`
- 输出格式：JSON + Markdown

## 检查范围

- PostgreSQL Store opt-in：`STORAGE_BACKEND=postgres` 与 `DATABASE_URL` 是否存在。
- Store Factory：task / approval / audit / metrics / graph checkpoint 的 PostgreSQL Store 与 SQLite fallback 文件是否存在。
- Alembic migration precheck：仅索引 `alembic/versions/*.py` 文件名与数量，不执行迁移。
- Redis opt-in：`REDIS_ENABLED` 与 `REDIS_URL` 是否存在。
- NoopRedisClient fallback：Redis 默认关闭与连接失败 fallback 代码路径是否存在。
- 限流存储边界：默认限流后端为 memory；v4.4 起具备 `RATE_LIMIT_BACKEND=redis` opt-in 路径，多实例生产仍需真实 Redis 或网关级限流验收。
- Deployment guard：PostgreSQL、Redis、request size、rate limit 等生产门禁测试证据是否存在。
- 审计与指标存储边界：SQLite / PostgreSQL audit 与 metrics store 文件和测试是否存在。
- Compose 文件：`docker-compose.yml` 与 `docker-compose.prod.yml` 是否存在。

## 边界

- 不连接真实 PostgreSQL。
- 不连接真实 Redis。
- 不执行 Alembic migration。
- 不写入业务数据、审计数据或指标数据。
- 不读取或输出 `DATABASE_URL`、`REDIS_URL`、`JWT_SECRET` 等 secret 原文。
- 不默认启用 PostgreSQL 或 Redis。
- 不宣称 PostgreSQL、Redis 或多实例限流生产验收完成。

## 运行方式

```powershell
python scripts/store_redis_readiness_drill.py
```

指定输出目录：

```powershell
python scripts/store_redis_readiness_drill.py --output-dir docs/reports/store_redis_readiness_drill
```

## 状态语义

- `skipped`：缺少显式 opt-in 条件，例如未设置 `STORAGE_BACKEND=postgres`、`DATABASE_URL`、`REDIS_ENABLED=true` 或 `REDIS_URL`。
- `partial`：本地工程证据齐备，且 opt-in 条件存在；仍未执行真实连接、迁移或写入。
- `blocked`：输出中检测到 secret-like 文本或出现不可接受边界风险。
- `failed`：脚本运行异常或输出无法生成。
- `success`：仅保留为状态词，不用于默认离线验收伪造成生产成功。

## 推荐回归

```powershell
python -m pytest tests/test_store_redis_readiness_drill_v374.py -q
python -m pytest tests/test_storage_v20.py tests/test_config_v20.py tests/test_deployment_guard_v60.py tests/test_request_guards_v72.py tests/test_runtime_persistence_v05.py -q
python scripts/store_redis_readiness_drill.py
```

## Go / No-Go 口径

- Go：脚本可生成脱敏 JSON/Markdown，缺少真实 opt-in 时清楚标记 `skipped`，默认离线路径不变。
- No-Go：输出 secret 原文、连接真实 PostgreSQL/Redis、执行真实迁移、写业务数据、把只读演练宣称为生产验收完成，或把 memory/本地 Redis backend 单测宣称为多实例生产限流完成。

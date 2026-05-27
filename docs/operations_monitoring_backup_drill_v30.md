# v3.0 Phase 10.3：运维监控与备份恢复演练记录

## 1. 演练目标

- 形成可复用的 runbook：日志、metrics、audit export、pilot report export 均可检查。
- 提供 SQLite / PostgreSQL / Redis 的备份与恢复演练模板命令。
- 明确数据留存、脱敏导出、清理边界，避免误删与泄漏。
- 本阶段仅做本地/内网试点级演练，不引入复杂运维平台。

## 2. 监控检查项（Runbook）

- 应用健康：`GET /health`
- 生产门禁：`GET /deployment/check`
- 运行指标：`GET /metrics/runtime`
- 试点报告只读：`GET /llm/pilot/reports`
- 审计导出：`GET /audit/events/export`
- 结构化日志与链路追踪：检查 `X-Request-ID`，日志中仅保留脱敏字段

说明：

- 如服务未启动，本轮记录为“未执行在线端点访问，仅做离线命令/测试验证”。
- 默认 fake/offline，不执行真实外网 LLM，不接真实外部 MCP 作为默认依赖。

## 3. 备份恢复演练

### 3.1 SQLite（默认开发路径）

- 数据文件位置以当前配置为准（常见为项目 `data/` 目录下 sqlite 文件）。
- 备份模板：
  - 停止写入或停服务后，复制 sqlite 文件到备份目录（如 `backups/sqlite/`）。
- 恢复模板：
  1. 停服务；
  2. 用备份文件替换目标 sqlite 文件；
  3. 启动服务后检查 `/health` 与关键接口。

### 3.2 PostgreSQL（试点/生产模板）

- 仅给出模板命令，不写真实连接串或密码：
  - 备份：`pg_dump "<POSTGRES_DSN>" > backup.sql`
  - 恢复：`psql "<POSTGRES_DSN>" -f backup.sql`
- 恢复前后建议执行：
  - `/deployment/check`
  - 关键业务 smoke
  - 审计导出抽样校验

### 3.3 Redis（缓存/限流相关）

- 内网试点可选 RDB/AOF 或 `redis-cli --rdb` 模板方式。
- 模板命令（不含真实密码）：
  - `redis-cli -h <host> -p <port> --rdb backup.rdb`
- 恢复流程按环境策略执行，先在演练环境验证再用于正式环境。

## 4. 数据留存与清理边界

- 审计留存遵循 `AUDIT_RETENTION_*` 配置与审计策略。
- `GET /audit/events/export` 必须保持白名单字段 + 脱敏 detail。
- `docs/reports/real_llm_pilot/` 报告目录需归档管理，清理前先备份。
- 禁止导出 prompt 原文、API key/token/secret/password/数据库密码原文。
- 不删除用户数据；任何清理动作前必须先备份并记录操作人/时间。

## 5. 本轮演练记录（2026-05-27）

- executed：`python -m pytest tests/test_runtime_hardening_v055.py -q`
- executed：`python -m pytest tests/test_audit_retention_export_v74.py -q`
- executed：`python -m pytest tests/test_llm_pilot_reports_v94.py -q`
- executed：`python -m pytest -q`
- executed：`docker compose config`
- skipped：在线端点直接访问（本轮未启动服务，未执行 `/health`、`/deployment/check`、`/metrics/runtime`、`/llm/pilot/reports`、`/audit/events/export` 实时请求）
- notes：本轮完成离线命令与测试验证，未执行真实外网 LLM

## 6. 结果模板（复用）

- executed/skipped
- command
- result
- notes
- operator
- timestamp

## 7. 边界声明

- 不提交 JWT_SECRET、DATABASE_URL、REDIS_URL、API key、client_secret 等真实凭据。
- 不执行真实外网 LLM。
- 不接真实外部 MCP 作为默认依赖。
- 不宣称公网生产可直接上线。
- 不宣称完整生产级 SSO/OIDC、多租户、复杂 BI 已完成。

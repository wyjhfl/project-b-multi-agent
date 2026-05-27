# v3.1 Phase 11.5：备份恢复检查清单

## 1. 使用范围

- 面向企业内网试点/准生产演示的备份恢复演练。
- 仅提供模板命令与检查步骤，不包含真实凭据。
- 所有步骤默认遵循：**不删除用户数据**。

## 2. SQLite 备份与恢复

### 2.1 备份

1. 停止写入高峰（可选短暂停机窗口）。
2. 复制数据库文件到备份目录：
   - `data/db/runtime.sqlite`
   - `data/db/runtime_metrics.sqlite`
   - 其他本地 sqlite 文件（按实际配置）
3. 记录备份时间、操作者、文件校验值。

### 2.2 恢复

1. 停服务（如 `docker compose stop app`）。
2. 备份当前数据库文件（防止二次回滚无基线）。
3. 用备份文件替换目标 sqlite 文件。
4. 启动服务并执行验证（见第 6 节）。

---

## 3. PostgreSQL 备份与恢复模板（占位符）

> 仅模板，禁止写真实连接串入仓库。

### 3.1 备份模板（pg_dump）

```bash
pg_dump "postgresql://<user>:<password>@<host>:<port>/<db>" -Fc -f /backup/<project>_<date>.dump
```

### 3.2 恢复模板（psql/pg_restore）

```bash
pg_restore -d "postgresql://<user>:<password>@<host>:<port>/<db>" /backup/<project>_<date>.dump
```

或

```bash
psql "postgresql://<user>:<password>@<host>:<port>/<db>" -f /backup/<project>_<date>.sql
```

---

## 4. Redis 备份与恢复模板（占位符）

### 4.1 RDB/AOF 说明

- 内网试点可使用 RDB 或 AOF 机制。
- 备份/恢复前记录实例版本与配置模式。

### 4.2 `redis-cli --rdb` 模板

```bash
redis-cli -h <host> -p <port> --rdb /backup/<project>_<date>.rdb
```

> 如需密码，使用安全注入方式，不写入脚本/仓库。

---

## 5. 审计导出与 pilot report 归档边界

- 审计导出保持白名单 + 脱敏边界：
  - `GET /audit/events/export`
  - `AUDIT_EXPORT_REDACTION_ENABLED=true`
- pilot 报告目录：
  - `docs/reports/real_llm_pilot/` 或 `REAL_LLM_PILOT_REPORT_DIR`
- 严禁归档以下原文：
  - prompt/query 原文
  - API key/token/client_secret
  - 数据库/Redis 密码原文

---

## 6. 恢复后验证命令

建议最小验证：

```bash
python -m pytest tests/test_runtime_hardening_v055.py -q
python -m pytest -q
docker compose config
```

在线验证（服务已启动时）：

- `GET /health`
- `GET /deployment/check`
- `GET /operations/summary`
- `GET /metrics/runtime`
- `GET /audit/events/export`（确认脱敏策略）
- `GET /llm/pilot/reports`

---

## 7. 回滚与清理临时变量

1. 发现恢复异常时，回滚到“恢复前临时备份”版本。
2. 清理本轮临时环境变量（如 `JWT_SECRET`、`DATABASE_URL`、`REDIS_URL`、`OIDC_CLIENT_SECRET`）。
3. 记录回滚原因、时间、影响范围。
4. 全程保持：**不删除用户数据**。

---

## 8. 边界声明

- 不提交真实 `DATABASE_URL`、`REDIS_URL`、`JWT_SECRET`、`API key`、`client_secret`。
- 不执行真实外网 LLM。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。


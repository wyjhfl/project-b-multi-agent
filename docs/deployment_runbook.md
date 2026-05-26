# 部署运行手册（v2.6 / Phase 6.0）

## 1. 适用范围

- 适用于 Project B 在企业内网试点环境的准生产部署演练。
- 不适用于公网生产直接上线。

## 2. 开发演示启动方式（默认离线路径）

```bash
docker compose up -d app frontend
```

- 使用 `docker-compose.yml`。
- 默认 `AUTH_ENABLED=false`、`RBAC_ENABLED=false`，便于本地离线演示。

## 3. 生产模板启动方式（试点）

### 3.1 准备环境变量

1. 复制 `.env.production.example` 为本地私有文件（例如 `.env.production`）。
2. 在部署环境注入真实安全变量，不要提交真实凭据文件。

### 3.2 执行部署脚本

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prod_up.ps1
```

- `prod_up.ps1` 会先执行 `prod_config_check.ps1`（默认本地 Python 检查），再执行 compose 启动。

### 3.3 手动命令等价

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build app frontend
```

## 4. 生产必填变量策略（docker-compose.prod.yml）

`docker-compose.prod.yml` 对以下敏感变量使用必填校验：

- `JWT_SECRET=${JWT_SECRET:?JWT_SECRET is required}`
- `DATABASE_URL=${DATABASE_URL:?DATABASE_URL is required}`
- `REDIS_URL=${REDIS_URL:?REDIS_URL is required}`

缺失时 `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` 会直接失败。

非敏感默认值保留：

- `APP_ENV=production`
- `DEBUG=false`
- `AUTH_ENABLED=true`
- `RBAC_ENABLED=true`
- `MCP_MODE=fake`
- `REAL_LLM_ACCEPTANCE_ENABLED=false`

新增安全基线配置（Phase 7.1）：

- `CORS_ENABLED=true`
- `CORS_ALLOW_ORIGINS` 必须配置明确来源，production 禁止使用 `*`
- `SECURITY_HEADERS_ENABLED=true`

新增请求防护配置（Phase 7.2）：

- `REQUEST_SIZE_LIMIT_ENABLED=true`
- `REQUEST_SIZE_LIMIT_BYTES=1048576`（可按业务调优，production 建议不超过 10MB）
- `RATE_LIMIT_ENABLED=true`（production 建议开启）
- `RATE_LIMIT_REQUESTS_PER_MINUTE`、`RATE_LIMIT_BURST` 按流量基线配置
- `RATE_LIMIT_EXEMPT_PATHS=/health`（可扩展）
- `ABUSE_GUARD_ENABLED=true`
- request guard 拦截响应（429/413/400/414）默认也会附带安全响应头，并在允许来源时返回对应 CORS 响应头。

新增结构化日志配置（Phase 7.3）：

- `STRUCTURED_LOGGING_ENABLED=true`
- `LOG_LEVEL=INFO`（production 不允许 `DEBUG`）
- `LOG_INCLUDE_CLIENT_IP=true`
- `LOG_INCLUDE_USER_AGENT=true`
- `LOG_REDACTION_ENABLED=true`

## 5. 配置检查脚本

```powershell
# 默认：本地 Python 检查（读取当前 shell 环境变量）
powershell -ExecutionPolicy Bypass -File scripts/prod_config_check.ps1

# 可选：显式改用本地 API 检查
powershell -ExecutionPolicy Bypass -File scripts/prod_config_check.ps1 -UseApi
```

输出包含：

- `environment`
- `ok`
- `warnings`
- `errors`

约束：

- 检查失败时退出码为 1。
- 不输出密钥、token、完整连接串密码。

## 6. Smoke 检查

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prod_smoke.ps1
```

覆盖端点：

- `http://localhost:3000/api/health`
- `http://localhost:3000/`
- `http://localhost:3000/tasks`
- `http://localhost:3000/approvals`
- `http://localhost:3000/rbac`
- `http://localhost:3000/tools`
- `http://localhost:3000/nl2sql`
- `http://localhost:3000/audit`
- `http://localhost:3000/metrics`
- `http://localhost:3000/observability`
- `http://localhost:8000/deployment/check`

## 7. 常见失败与处理

- `deployment/check` 返回 `ok=false`：按 `errors` 逐条修复配置后重试。
- `JWT_SECRET` 报错：检查是否仍使用占位值或长度不足。
- `DATABASE_URL/REDIS_URL` 报错：检查开关是否启用且 URL 非空，且未使用占位密码。
- 前端页面 5xx：先检查 `http://localhost:3000/api/health` 与 `http://localhost:8000/health`。

## 8. 停止与回滚

### 8.1 停止

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prod_down.ps1
```

### 8.2 回滚建议

- 保留上一版 compose 镜像与环境变量文件。
- 回滚后重新执行：
  - `prod_config_check.ps1`
  - `prod_up.ps1`

## 9. 边界声明

- 默认路径仍为离线演示，不依赖真实 LLM 与真实外部 MCP。
- 真实 LLM smoke 为 opt-in，不进入默认 CI。
- 本手册不包含生产级 SSO/OIDC、多租户、复杂 BI 方案。
- 当前已完成安全基线前三步（Phase 7.1 CORS/安全响应头 + Phase 7.2 请求防护 + Phase 7.3 结构化日志与脱敏），但仍不等于完整公网生产安全基线完成。
- 当前限流为进程内内存版，适用于单实例内网试点；多实例生产应升级为 Redis 或网关级限流。
- 当前日志为应用层 stdout JSON，生产集中采集仍需接入外部日志系统。

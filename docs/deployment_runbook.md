# 部署运行手册（v2.6 / Phase 6.0）

## 1. 适用范围

- 适用于 Project B 在企业内网试点环境的准生产部署演练。
- 不适用于公网生产直接上线。

## 2. 开发演示启动方式（默认离线路径）

```bash
docker compose up -d app frontend
```

- 使用 `docker-compose.yml`。
- 默认 `AUTH_ENABLED=false`、`RBAC_ENABLED=false`，便于本地演示。

## 3. 生产模板启动方式（试点）

### 3.1 准备环境变量

1. 复制 `.env.production.example` 为本地私有文件（例如 `.env.production`）。
2. 按试点环境填充真实值（不要提交到仓库）。

### 3.2 执行部署

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prod_up.ps1
```

- 脚本会先执行 `prod_config_check.ps1`，再执行 compose up。

### 3.3 手动命令等价

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build app frontend
```

## 4. 必需环境变量（production）

- `APP_ENV=production`
- `AUTH_ENABLED=true`
- `RBAC_ENABLED=true`
- `JWT_SECRET`（必须替换默认占位值）
- `STORAGE_BACKEND=postgres` 时 `DATABASE_URL`
- `REDIS_ENABLED=true` 时 `REDIS_URL`
- `MCP_MODE=real` 时 `MCP_SERVER_COMMAND_ALLOWLIST`
- `REAL_LLM_ACCEPTANCE_ENABLED=true` 时 `REAL_LLM_MODEL` 与 `REAL_LLM_API_KEY_ENV` 指向的环境变量

## 5. 配置检查

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prod_config_check.ps1
```

- 检查通过：退出码 0。
- 检查失败：退出码 1，并输出结构化错误摘要。
- 不输出密钥原文。

## 6. Smoke 检查

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prod_smoke.ps1
```

检查以下端点：

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

- `deployment/check` 返回 `ok=false`：
  - 按 `errors` 项逐条修正配置后重试。
- `JWT_SECRET` 报错：
  - 检查是否仍使用开发占位值。
- `DATABASE_URL/REDIS_URL` 报错：
  - 确认对应开关已启用且 URL 非空。
- 前端页面 5xx：
  - 先检查 `http://localhost:3000/api/health` 与 `http://localhost:8000/health`。

## 8. 停止与回滚

### 8.1 停止

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prod_down.ps1
```

### 8.2 回滚建议

- 保留上一版 compose 镜像与环境变量文件。
- 回滚到上一稳定提交后，重新执行：
  - `prod_config_check.ps1`
  - `prod_up.ps1`

## 9. 边界声明

- 默认路径仍为离线演示，不依赖真实 LLM 与真实外部 MCP。
- 真实 LLM smoke 仅 opt-in，不进入默认 CI。
- 本手册不包含生产级 SSO/OIDC、多租户、复杂 BI 方案。

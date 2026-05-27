# v3.0 Phase 10.2：生产部署演练与回滚记录

## 1. 演练目标

- 以文档化演练与脚本验证方式，收口生产部署与回滚流程。
- 验证 deployment guard、compose 配置检查、基础健康检查路径是否可执行。
- 保持默认开发路径不变，不引入真实外网 LLM 与真实外部 MCP 依赖。

## 2. 演练环境说明

- 演练环境：本地/企业内网试点模拟环境。
- 本文档不代表公网生产上线批准。
- 本轮不要求公网域名，不要求真实企业 IdP，不执行真实外网 LLM。

## 3. 使用文件与脚本

- `.env.production.example`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `scripts/prod_config_check.ps1`
- `scripts/prod_up.ps1`
- `scripts/prod_smoke.ps1`
- `scripts/prod_down.ps1`

## 4. 必需变量清单（production）

- `APP_ENV=production`
- `JWT_SECRET`
- `DATABASE_URL`
- `REDIS_URL`
- `AUTH_ENABLED=true`
- `RBAC_ENABLED=true`

补充边界：

- 真实 LLM 默认关闭（`REAL_LLM_ACCEPTANCE_ENABLED=false`）。
- 真实外部 MCP 默认关闭（`MCP_MODE=fake`）。

## 5. 演练步骤

### 5.1 启动前配置检查

1. 执行基础 compose 校验：
   - `docker compose config`
2. 执行 production override 校验（缺变量应失败）：
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`
3. 注入临时安全占位变量后再次校验（应通过）：
   - `JWT_SECRET`：长度 >= 32 的测试值
   - `DATABASE_URL`：本地测试 postgres URL
   - `REDIS_URL`：本地测试 redis URL
4. 执行 `scripts/prod_config_check.ps1`：
   - development 默认：通过或 warning 通过
   - production 缺配置：失败
   - production 临时合法配置：通过

### 5.2 启动与 smoke（可选）

- 可选执行 `docker compose build app frontend` 做镜像构建验证。
- 如执行 `prod_up.ps1` / `prod_smoke.ps1`，必须在结束后执行 `prod_down.ps1`。
- 本轮不强制执行 `up`，避免不必要资源占用。

### 5.3 停止与回滚

1. 停止生产覆盖 compose：
   - `powershell -ExecutionPolicy Bypass -File scripts/prod_down.ps1`
2. 回退默认开发 compose 路径：
   - 使用 `docker compose.yml` 默认启动方式
3. 清理当前 shell 临时环境变量：
   - `JWT_SECRET` / `DATABASE_URL` / `REDIS_URL`
4. 不删除用户数据卷与业务数据文件。

## 6. 失败场景预期

- 缺 `JWT_SECRET`：应失败。
- 缺 `DATABASE_URL`：应失败。
- 缺 `REDIS_URL`：应失败。
- 临时合法变量注入后：config check 应通过。

## 7. 本轮演练结果（2026-05-27）

- `docker compose config`：通过。
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`（缺变量）：按预期失败（缺 `DATABASE_URL` 或 `REDIS_URL`）。
- 注入临时 `JWT_SECRET` / `DATABASE_URL` / `REDIS_URL` 后 prod compose config：通过。
- `scripts/prod_config_check.ps1`（development 默认）：通过（warning 通过）。
- `scripts/prod_config_check.ps1`（production 缺配置）：按预期失败。
- `scripts/prod_config_check.ps1`（production 临时合法配置）：通过。
- 本轮未执行 `prod_up.ps1` / `prod_smoke.ps1` / `prod_down.ps1` 实际容器演练（仅脚本与配置验证）。
- 本轮未执行真实外网 LLM。

## 8. 演练结果模板（复用）

- executed / skipped
- command
- result
- notes
- operator
- timestamp

## 9. 边界声明

- 不提交任何真实密钥（JWT_SECRET、DATABASE_URL、REDIS_URL、API key、client_secret）。
- 不执行真实外网 LLM。
- 不宣称公网生产可直接上线。
- 不宣称完整生产级 SSO/OIDC、多租户、复杂 BI 已完成。

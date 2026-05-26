# v2.6 / Phase 6.0 工程化落地计划

## 1. 目标与定位

- 对齐 v3.0 生产路线第一阶段：将 v2.5.0 既有能力收敛为“企业内网试点准生产可投入使用”形态。
- 保持默认离线开发路径不变：默认 fake/offline，默认 pytest 不调用真实 LLM。
- 本阶段不是公网生产级 SaaS，不宣称可直接公网上线。

## 2. 分阶段关系（v3.0 视角）

- v2.5.0：完成真实 LLM 可选验收包（opt-in）。
- v2.6.0（当前）：工程化落地，补齐部署门禁、生产模板、运维脚本、CI 收敛。
- v3.0 后续阶段：再逐步推进更高等级生产能力（不在本阶段实现）。

## 3. Phase 6.0 交付范围

- 部署门禁：`app/core/deployment_guard.py` + `GET /deployment/check`。
- 健康检查增强：`/health` 增加 `rbac_enabled`。
- 生产模板：`.env.production.example`、`docker-compose.prod.yml`。
- 运维脚本：`scripts/prod_config_check.ps1`、`scripts/prod_up.ps1`、`scripts/prod_smoke.ps1`、`scripts/prod_down.ps1`。
- CI 工程化增强：在后端 pytest 基础上补充前端 lint/build 与 compose config 校验。

## 4. 部署门禁策略

### 4.1 development 环境

- `APP_ENV=development` 时仅给 warning，不阻断默认测试与默认演示路径。

### 4.2 production 环境

- `JWT_SECRET` 不能为空、不能为占位值、长度不少于 32。
- `AUTH_ENABLED=true` 且 `RBAC_ENABLED=true`。
- `STORAGE_BACKEND=postgres` 时 `DATABASE_URL` 必须非空且不能含占位密码。
- `REDIS_ENABLED=true` 时 `REDIS_URL` 必须非空且不能含占位值。
- `MCP_MODE=real` 时 `MCP_SERVER_COMMAND_ALLOWLIST` 必须非空。
- `REAL_LLM_ACCEPTANCE_ENABLED=true` 时：
  - `REAL_LLM_MODEL` 必须非空；
  - `REAL_LLM_API_KEY_ENV` 必须配置且对应环境变量存在。

### 4.3 安全约束

- 部署检查返回结构化结果，不抛 500。
- 返回结果与日志不输出 API key、token、数据库密码原文。

## 5. 配置模板与部署形态

### 5.1 默认开发模板

- `docker-compose.yml`
- 特点：离线友好、演示优先、默认 auth/rbac 关闭。

### 5.2 生产试点 override 模板

- `docker-compose.yml + docker-compose.prod.yml`
- 特点：显式 production 配置、门禁约束可校验、仍不默认启用真实 LLM/MCP。

### 5.3 环境变量模板

- `.env.production.example` 只放占位说明，不提交真实 `.env.production`。

## 6. CI/CD 收敛

- 保留：后端 `python -m pytest -q`。
- 新增：前端 `npm ci && npm run lint && npm run build`。
- 新增：`docker compose config` 与 prod override config 校验。
- 默认环境维持 `MCP_MODE=fake`、`LLM_PROVIDER=fake`、`REAL_LLM_SMOKE_ENABLED=false`，不跑真实 LLM smoke。

## 7. 交付验收标准

- 代码：部署门禁、API、健康检查、模板、脚本、CI 均已落地。
- 测试：相关 pytest 通过，默认路径不触发真实 LLM。
- 运行：compose config 可解析，prod 脚本可执行并输出结构化检查结果。
- 文档：runbook 与 readiness checklist 齐备，边界声明一致。
- 当前测试口径：**671 passed, 4 skipped**（默认 real_llm 用例 skip）。

## 8. 明确边界

- 不做生产级 SSO/OIDC。
- 不做多租户。
- 不做复杂 BI。
- 不宣称真实外部 MCP Server 生产验收完成。
- 不宣称真实 LLM 生产验收完成。
- 不宣称公网生产可直接上线。

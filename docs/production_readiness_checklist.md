# 生产就绪检查清单（v2.6 / Phase 6.0）

> 目标：用于企业内网试点的准生产可投入使用检查，不等于公网生产上线批准。

## 1. 配置安全

- [ ] `APP_ENV=production`
- [ ] `JWT_SECRET` 已替换默认开发占位值
- [ ] 未提交真实 `.env.production`
- [ ] 未在日志/脚本输出中暴露密钥原文

## 2. 鉴权与 RBAC

- [ ] `AUTH_ENABLED=true`
- [ ] `RBAC_ENABLED=true`
- [ ] `/health` 返回包含 `rbac_enabled`
- [ ] 关键接口权限行为符合 `require_permission` 规则

## 3. 数据库与 Redis

- [ ] `STORAGE_BACKEND=postgres` 时 `DATABASE_URL` 非空
- [ ] `REDIS_ENABLED=true` 时 `REDIS_URL` 非空
- [ ] compose 依赖与 healthcheck 正常

## 4. LLM（opt-in）边界

- [ ] 默认 `REAL_LLM_ACCEPTANCE_ENABLED=false`
- [ ] 默认测试不调用真实 LLM
- [ ] 若开启真实 LLM 验收，需显式配置 model 与 API key 环境变量
- [ ] 不提交 API key / token

## 5. MCP fake/real 边界

- [ ] 默认 `MCP_MODE=fake`
- [ ] `MCP_MODE=real` 时 `MCP_SERVER_COMMAND_ALLOWLIST` 非空
- [ ] 不把真实外部 MCP 作为默认依赖

## 6. 审计与指标

- [ ] `/deployment/check` 可返回结构化门禁结果
- [ ] 配置错误返回 `ok=false` 且 HTTP 200，不抛 500
- [ ] Runtime metrics 与 audit/trace 基础能力可访问

## 7. 前端页面可用性

- [ ] 首页与导航可访问
- [ ] Tasks / Approvals / Audit / Metrics / Observability 可访问
- [ ] Tools / NL2SQL 页面可访问
- [ ] `/api/health` 代理可访问

## 8. CI 验证

- [ ] 后端 `python -m pytest -q` 通过
- [ ] 前端 `npm ci && npm run lint && npm run build` 通过
- [ ] `docker compose config` 通过
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` 通过

## 9. 运维脚本验证

- [ ] `scripts/prod_config_check.ps1` 可执行并输出结构化结果
- [ ] `scripts/prod_up.ps1` 可完成启动
- [ ] `scripts/prod_smoke.ps1` 可完成端点 smoke
- [ ] `scripts/prod_down.ps1` 可停止清理

## 10. 当前未完成项（必须保留）

- [ ] 生产级 SSO/OIDC
- [ ] 多租户
- [ ] 复杂 BI
- [ ] 真实外部 MCP Server 生产验收
- [ ] 真实 LLM 生产验收完成声明（禁止）

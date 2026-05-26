# RELEASE NOTES v2.6.0

## 1. Highlights

- 完成 Phase 6.0 Engineering Readiness 收口，版本定位为“企业内网试点准生产可投入使用”。
- 保持默认离线/演示路径不变，不破坏 v2.5.0 已有能力。
- 当前验证基线：**671 passed, 4 skipped**（默认 real_llm 用例 skip）。

## 2. Engineering Readiness

- 部署门禁、生产模板、运维脚本、CI 校验链路形成最小闭环。
- 默认路径仍为 fake/offline，不依赖真实外部 MCP 与真实 LLM。

## 3. Deployment Guard

- `app/core/deployment_guard.py` 增强 production 校验：
  - JWT_SECRET 禁止占位值与短密钥；
  - postgres/redis 开关下强制连接配置并拦截占位口令；
  - 保持 development 环境 warning-only。
- 错误信息不回显密钥、token 或连接串密码。

## 4. /deployment/check 与 /health 增强

- `GET /deployment/check` 始终返回结构化结果（配置错误时 `ok=false`，HTTP 200）。
- `/health` 返回版本号与 `rbac_enabled` 等关键运行态字段。

## 5. Production env / compose override

- `docker-compose.prod.yml` 对敏感变量启用必填策略：
  - `JWT_SECRET`、`DATABASE_URL`、`REDIS_URL`。
- `.env.production.example` 仅保留占位说明，明确真实变量需由部署环境注入。

## 6. Prod scripts

- `scripts/prod_config_check.ps1` 默认本地 Python 检查，避免误读旧运行实例。
- 支持可选 `-UseApi` 显式调用 `/deployment/check`。
- `scripts/prod_up.ps1` 先检查后启动，保持默认安全顺序。

## 7. CI 增强

- 保持后端 `pytest` 全量执行。
- 保持前端 `npm run lint` / `npm run build` 校验链路。
- 增加 compose 与 prod override config 可解析性验证。

## 8. 文档与 runbook

- 更新部署 runbook 与工程化计划文档，统一 v2.6.0 阶段口径。
- 明确“企业内网试点准生产可投入使用”与非公网生产边界。

## 9. Verification

- `python -m pytest tests/test_deployment_guard_v60.py -q`
- `python -m pytest tests/test_runtime_hardening_v055.py -q`
- `python -m pytest tests/test_llm_preflight_v51.py tests/test_real_llm_smoke_v52.py tests/test_real_llm_judge_smoke_v54.py -q`
- `python -m pytest -q`
- `docker compose config`
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`（缺变量失败 / 注入临时安全变量通过）
- `frontend`: `npm run lint`、`npm run build`
- `powershell -ExecutionPolicy Bypass -File scripts/prod_config_check.ps1`（development warning 通过，production 合法配置通过）

## 10. Known boundaries

- 本版本定位为企业内网试点准生产可投入使用，不等于公网生产可直接上线。
- 不包含生产级 SSO/OIDC。
- 不包含多租户。
- 不包含复杂 BI。
- 不包含真实外部 MCP Server 生产验收完成声明。
- 真实 LLM 仍为 opt-in 验收，不进入默认路径与默认测试。

## 11. Upgrade notes

- 版本号同步到 `2.6.0`：`pyproject.toml`、FastAPI `app.version`、`/health.version`、MCP stdio client fallback 版本与测试断言。
- 文档口径同步到 v2.6.0 工程化阶段与 671 passed, 4 skipped 基线。

## 12. Next phase

- 建议进入 v2.6.0 tag 决策流程（本轮仅 release prep，不打 tag，不创建 GitHub Release）。

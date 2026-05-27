# v2.7 Security Baseline Release Review

## 1. Scope

本次 review 覆盖 v2.7.0 的 Production Security Baseline 交付范围：

- Phase 7.1 CORS 与安全响应头
- Phase 7.2 request size limit / rate limit / basic abuse guard
- Phase 7.3 结构化日志与日志脱敏
- Phase 7.4 审计留存策略与 JSONL 导出边界
- Phase 7.5 OIDC/SSO 最小接入骨架与配置预检

不包含：生产级 SSO/OIDC 完整对接、多租户、复杂 BI、真实外部 MCP 生产验收、真实 LLM 生产验收。

## 2. Changed modules

- 安全中间件与请求防护：`app/core/security_headers.py`、`app/core/request_guards.py`、`app/core/request_logging.py`、`app/core/structured_logging.py`
- 审计留存与导出：`app/harness/audit/retention.py`、`app/api/audit.py`
- OIDC 骨架与状态接口：`app/auth/oidc_config.py`、`app/api/oidc.py`
- 部署门禁与配置：`app/core/deployment_guard.py`、`app/core/config.py`、`.env.example`、`.env.production.example`
- 前端试点说明：`frontend/src/app/rbac/page.tsx`、`frontend/src/lib/api/system.ts`
- 文档与 runbook：`README.md`、`AGENTS.md`、`docs/production_security_baseline_plan_v27.md`、`docs/deployment_runbook.md`、`docs/production_readiness_checklist.md`

## 3. Verification matrix

- 后端定向测试：OIDC / audit export / structured logging / request guards / security headers / deployment guard / runtime hardening
- 后端全量测试：`python -m pytest -q` => `727 passed, 4 skipped`
- Docker：
  - `docker compose config` 通过
  - prod override 缺变量时失败（符合预期）
  - 临时注入安全变量后通过
- 前端：`npm run lint`、`npm run build` 通过

## 4. Security / privacy boundary

- 默认不记录 request body 与 prompt 原文。
- 默认不输出 API key、token、Authorization、Cookie、password、secret、database/redis 密码原文。
- 审计导出使用字段白名单 + 强制脱敏。
- OIDC status 仅返回 `client_secret_present` 布尔状态，不返回密钥原文。

## 5. Deployment readiness boundary

- v2.7.0 定位：企业内网试点准生产安全基线能力增强。
- 默认 fake/offline，默认 pytest 不调用真实 LLM。
- 默认不依赖真实外部 MCP。
- OIDC 默认关闭，不依赖真实外部 IdP。

## 6. Known limitations

- 当前 rate limit 为进程内内存版，不适用于多实例一致性限流场景。
- 当前 OIDC 为最小接入骨架与配置预检，不包含真实 token exchange 与完整企业 IdP 联调。
- 不包含生产级 SSO/OIDC、多租户、复杂 BI。
- 不等于完整公网生产安全基线，不宣称公网生产可直接上线。

## 7. Go / No-Go

结论：**Go（建议进入 v2.7.0 tag 决策）**。

说明：本轮完成了 v2.7.0 安全基线阶段交付与验证，满足“企业内网试点准生产安全基线能力增强”定位；本轮仅做 release prep，不在本文档内执行打 tag 或创建 GitHub Release。

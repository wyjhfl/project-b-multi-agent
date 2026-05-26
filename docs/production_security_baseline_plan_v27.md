# v2.7 Production Security Baseline 规划

## 1. 当前基础盘点（承接 v2.6）

v2.6.0 已具备以下工程化基础，可直接承接 v2.7 安全基线工作：

- 部署门禁：`deployment_guard` 与 `/deployment/check` 结构化检查。
- 生产模板：`docker-compose.prod.yml` + `.env.production.example`。
- 运维脚本：`prod_config_check.ps1`、`prod_up.ps1`、`prod_smoke.ps1`、`prod_down.ps1`。
- 默认离线路径稳定：`fake/offline`，默认 `pytest` 不调用真实 LLM。
- 运营台能力已闭环：Tasks / Approvals / Audit / Metrics / Tools / NL2SQL。

## 2. v2.7 总目标

在不破坏默认离线开发路径的前提下，分阶段补齐“企业内网试点准生产可投入使用”的安全基线能力，提升配置安全、请求防护、日志可观测与审计边界清晰度。

## 3. Phase 7.1：CORS 与安全响应头（已完成）

已完成内容：

- 引入可配置 CORS 策略（development 默认允许 `http://localhost:3000`）。
- 生产环境限制 CORS，禁止 wildcard（`*`）作为允许来源。
- 全局安全响应头中间件生效，覆盖核心 API（如 `/health`、`/deployment/check` 等）。
- 已有测试覆盖 CORS preflight 与安全响应头返回行为。

## 4. Phase 7.2：请求防护（已完成）

已完成内容：

- `RequestSizeLimitMiddleware`：请求体大小限制，超限返回 `413 request_too_large`。
- `RateLimitMiddleware`：基础限流，超限返回 `429 rate_limited`。
- `BasicAbuseGuardMiddleware`：基础滥用防护（异常 path/header）返回 `400/414`。
- guard 拦截响应（`429/413/400/414`）同样覆盖安全响应头。
- 对允许来源（如 `http://localhost:3000`）的 guard 拦截响应同样返回 CORS 头。

约束说明：

- 当前 rate limit 为**进程内内存版**，适合单实例内网试点。
- 多实例生产需升级为 Redis 或网关级限流方案（如 API Gateway / Ingress 限流）。
- 本阶段不等于完整 WAF 能力，不替代专业边界防护系统。

## 5. Phase 7.3：结构化日志与日志脱敏（规划中）

目标：

- 统一结构化日志字段（如 `request_id`、`task_id`、`actor`、`action`、`result`）。
- 对敏感信息（`token`、`api_key`、`authorization`、数据库密码等）做统一脱敏。
- 明确默认日志级别与开发/试点环境差异配置。

## 6. Phase 7.4：审计留存策略与导出边界（规划中）

目标：

- 明确审计数据记录范围、留存周期、滚动策略。
- 定义审计导出字段白名单与脱敏边界。
- 明确导出接口/脚本权限边界与操作说明。

## 7. Phase 7.5：OIDC/SSO 规划或最小接入方案（规划中）

目标：

- 输出最小 OIDC/SSO 接入设计（身份源、回调、角色映射）。
- 说明与现有 JWT/RBAC 的兼容策略。
- 给出试点接入 checklist 与风险清单。

说明：本阶段仅做规划与最小接入方案评估，不宣称生产级 SSO/OIDC 已完成。

## 8. Phase 7.6：v2.7 release prep（规划中）

目标：

- 收口版本口径、验证口径与边界声明。
- 整理 runbook、release notes、release review 与交接材料。
- 形成可审阅、可交接的发版前检查清单。

## 9. 当前边界与不做项

- 默认离线路径不变，默认 `pytest` 不调用真实 LLM。
- 不提交 API key、token、账号凭据到仓库。
- 不将真实外部 MCP 作为默认依赖。
- 不宣称公网生产可直接上线，不承诺完整公网生产 SLA。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 已完成。
- 不宣称真实 LLM、真实外部 MCP 已完成生产验收。

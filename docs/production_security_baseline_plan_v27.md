# v2.7 Production Security Baseline 规划

## 1. 当前基础盘点

v2.6.0 已形成可复用的工程化基础，作为 v2.7 安全基线的起点：

- 部署门禁：`deployment_guard` + `/deployment/check` 结构化检查。
- 生产模板：`docker-compose.prod.yml` + `.env.production.example`。
- 运维脚本：`prod_config_check.ps1`、`prod_up.ps1`、`prod_smoke.ps1`、`prod_down.ps1`。
- 默认运行路径：`fake/offline`，不依赖真实外部服务。
- 默认测试路径：`python -m pytest -q` 不调用真实 LLM。
- 运营台闭环能力：Tasks / Approvals / Audit / Metrics / Tools / NL2SQL。

## 2. v2.7 总目标

v2.7 的目标是补齐“企业内网试点准生产可投入使用”的安全基线能力，包括请求入口防护、日志脱敏、审计留存边界和发布前安全检查。

该目标不等于“完整公网生产安全基线”或“公网生产可直接上线”。

## 3. Phase 7.1：CORS 与安全响应头（已完成）

已完成内容：

- 引入 CORS allowlist 配置。
- development 默认允许 `http://localhost:3000`。
- production 禁止 `*` wildcard 作为允许来源。
- 安全响应头中间件覆盖核心 API，包括 `/health`、`/deployment/check` 等。
- 已有测试覆盖 CORS preflight 和安全响应头行为。

## 4. Phase 7.2：请求防护（已完成）

已完成内容：

- `RequestSizeLimitMiddleware`：请求体超限返回 `413 request_too_large`。
- `RateLimitMiddleware`：访问超限返回 `429 rate_limited`。
- `BasicAbuseGuardMiddleware`：异常 path/header 返回 `400/414`。
- `429/413/400/414` 拦截响应同样覆盖安全响应头。
- 允许来源（如 `http://localhost:3000`）下，拦截响应同样返回 CORS 响应头。

范围边界：

- 当前 rate limit 为进程内内存版，仅适合单实例内网试点。
- 多实例生产需升级为 Redis 或网关级限流。
- 本阶段不等于完整 WAF。

## 5. Phase 7.3：结构化日志与日志脱敏（已完成）

已完成内容：

- 新增请求级结构化日志中间件，统一输出 JSON 单行日志。
- 统一关键字段：`event_type`、`request_id`、`method`、`path`、`status_code`、`latency_ms`、`actor`。
- 可选扩展字段：`client_ip`、`user_agent`、`error_type`、`result`（如 `rate_limited` / `request_too_large` / `request_rejected`）。
- 所有请求生成或透传 `X-Request-ID`，并在响应头返回，便于链路排查。
- 对 guard 拦截响应（`429/413/400/414`）同样记录结构化日志并返回 `X-Request-ID`。
- 默认不记录 request body，不记录 prompt 原文，不记录密钥原文。
- 敏感信息脱敏覆盖：`authorization`、`cookie`、`set-cookie`、`token`、`access_token`、`refresh_token`、`api_key`、`password`、`secret`、`jwt`、`database_url`、`redis_url`。
- DSN 脱敏支持 PostgreSQL/Redis，保留定位上下文但不暴露密码明文。
- 新增测试覆盖日志脱敏、JSON 可解析、`X-Request-ID` 透传与 guard 响应链路。

范围边界：

- 当前日志输出为应用层 stdout JSON，生产集中采集仍需接入外部日志系统。

## 6. Phase 7.4：审计留存策略与导出边界（规划中）

规划方向：

- 明确审计事件留存范围、时长、轮转策略。
- 定义导出字段白名单和脱敏边界。
- 明确导出能力的权限边界与操作审计要求。

## 7. Phase 7.5：OIDC/SSO 规划或最小接入方案（规划中）

规划方向：

- 输出最小可落地的 OIDC/SSO 接入方案（身份源、回调、角色映射）。
- 评估与现有 JWT/RBAC 的兼容方式。
- 形成试点接入 checklist 与风险清单。

边界声明：本阶段仅做规划或最小接入方案，不宣称生产级 SSO/OIDC 已完成。

## 8. Phase 7.6：v2.7 release prep（规划中）

规划方向：

- 收口版本口径、测试口径、边界声明。
- 整理 runbook / release notes / release review / 交接材料。
- 形成 tag 前发布检查清单。

## 9. 当前边界与不做项

- 默认离线路径不变。
- 默认 `pytest` 不调用真实 LLM。
- 不提交 API key / token / 账号凭据。
- 不接真实外部 MCP 作为默认依赖。
- 不宣称公网生产可直接上线。
- 不承诺完整公网生产 SLA。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 已完成。
- 不宣称真实 LLM/真实外部 MCP 生产验收已完成。

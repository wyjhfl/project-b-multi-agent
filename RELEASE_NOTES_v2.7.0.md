# RELEASE_NOTES_v2.7.0

## Highlights

v2.7.0 完成 Production Security Baseline 阶段交付，覆盖 Phase 7.1 ~ 7.5：

- CORS 与安全响应头基线
- 请求防护（request size limit / rate limit / basic abuse guard）
- 结构化日志与敏感信息脱敏
- 审计留存策略与 JSONL 导出边界
- OIDC/SSO 最小接入骨架与配置预检

## Phase 7.1：CORS + 安全响应头

- 引入 CORS allowlist 配置，development 默认允许 `http://localhost:3000`。
- production 禁止 wildcard `*`。
- 统一覆盖 `X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy`、`Permissions-Policy`、`X-XSS-Protection`。
- guard 拦截响应同样覆盖安全响应头与允许来源 CORS 头。

## Phase 7.2：请求防护

- `RequestSizeLimitMiddleware`：超限返回 `413 request_too_large`。
- `RateLimitMiddleware`：超限返回 `429 rate_limited`。
- `BasicAbuseGuardMiddleware`：异常 path/header 返回 `400/414 request_rejected`。
- 当前限流为进程内内存版，适配单实例内网试点；多实例生产需 Redis 或网关级限流。

## Phase 7.3：结构化日志与日志脱敏

- 新增请求级 JSON 单行结构化日志。
- 统一链路字段：`event_type`、`request_id`、`method`、`path`、`status_code`、`latency_ms`、`actor`。
- 支持 `X-Request-ID` 透传与回写响应头。
- 默认不记录 request body / prompt 原文。
- 敏感字段与 DSN 密码脱敏，覆盖精确敏感键与常见组合敏感键。

## Phase 7.4：审计留存策略与导出边界

- 新增留存配置与校验：`audit_retention_enabled`、`audit_retention_days`。
- 新增导出配置：`audit_export_enabled`、`audit_export_max_rows`、`audit_export_format`、`audit_export_redaction_enabled`。
- 新增 `GET /audit/events/export`，默认 JSONL（`application/x-ndjson`）。
- 导出采用字段白名单 + 强制脱敏，不导出 prompt 原文和密钥原文。

## Phase 7.5：OIDC/SSO 最小接入骨架与配置预检

- 新增 OIDC 配置骨架（默认 `OIDC_ENABLED=false`）。
- 新增 OIDC 配置预检与角色映射函数。
- 新增 `GET /auth/oidc/status`，仅返回状态与布尔值，不返回 `client_secret` 原文。
- production 启用 OIDC 时，deployment guard 强制校验 issuer/client_id/redirect_uri/client_secret env/https 约束。

## 默认路径与安全边界

- 默认 fake/offline，默认测试不调用真实 LLM。
- 真实 LLM 仍为 opt-in 验收，不进入默认 CI。
- 默认不依赖真实外部 MCP。
- OIDC 默认关闭，不依赖真实外部 IdP。
- 不提交 API key、token、client_secret、账号凭据。

## 验证摘要

- 后端全量测试：`727 passed, 4 skipped`。
- 前端：`npm run lint`、`npm run build` 通过。
- `docker compose config` 通过。
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`：
  - 缺少必填变量时按预期失败。
  - 注入临时安全变量后通过。

## Known boundaries

- 当前定位为“企业内网试点准生产安全基线能力增强”。
- 不等于完整公网生产安全基线完成。
- 不宣称公网生产可直接上线。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 已完成。
- 不宣称真实 LLM/真实外部 MCP 生产验收已完成。

## Upgrade notes

- 升级到 v2.7.0 时，建议同步检查 CORS、安全头、请求防护、结构化日志、审计导出、OIDC 预检配置。
- 若生产启用 OIDC，必须注入 `OIDC_CLIENT_SECRET_ENV` 指向的环境变量并启用 https。

## Next phase

- 进入 v2.7.0 tag 决策与发布门禁复核。

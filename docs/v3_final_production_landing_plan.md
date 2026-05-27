# v3.0 Final Production Landing 规划

## 1. 当前已完成能力基线

- v2.6 Engineering Readiness：部署门禁、生产模板、prod 脚本与工程化检查链路。
- v2.7 Production Security Baseline：CORS/安全响应头、请求防护、结构化日志脱敏、审计留存与导出边界、OIDC 最小配置预检。
- v2.8 Controlled Real LLM Pilot：真实 LLM 受控试点入口与配置观测，默认仍 fake/offline。
- v2.9 Real LLM Controlled Pilot Evidence：试点证据模型、自动脱敏报告、NL2SQL/Judge/audit/metrics 证据串联、只读审查入口。

## 2. v3.0 目标定义

- 面向企业内网试点/准生产落地，强化“可运行、可回滚、可审计、可复盘”。
- 不等于公网 SaaS 生产直接上线。
- 不等于完整多租户/复杂 BI/生产级 SSO 全量完成。

## 3. v3.0 剩余主线

### Phase 10.1：真实 LLM 受控试点实测报告归档

- 用户手动 opt-in 执行真实 LLM smoke。
- 归档 `docs/reports/real_llm_pilot/` 报告与批次说明。
- 记录 provider/model/base_url 摘要、latency/tokens/cost/request_id/fallback/budget/cache。
- 严格保持边界：不提交密钥、不记录 prompt 原文。

### Phase 10.2：生产部署演练与回滚

- 使用 `.env.production.example`、`docker-compose.prod.yml` 与 prod 脚本进行演练。
- 检查 `/deployment/check`、`/health`、`/metrics/runtime`。
- 形成启动、smoke、停机、回滚完整步骤与执行记录。
- 不要求公网域名，不要求真实企业 IdP。

### Phase 10.3：运维监控与备份恢复

- 收口日志、metrics、audit export、report export 的运维操作基线。
- 补齐 DB/Redis 备份恢复演练文档与步骤记录。
- 明确数据留存与清理策略（含审计与报告目录）。
- 仅做演练与 runbook，不引入复杂运维平台改造。

### Phase 10.4：安全复核与 Go/No-Go

- 复核 deployment guard。
- 复核 CORS/security headers/rate limit/request size。
- 复核 structured logging redaction。
- 复核 audit export redaction。
- 复核 OIDC config preflight。
- 复核 LLM report redaction。
- 形成最终 Go/No-Go checklist。

### Phase 10.5：v3.0 release prep

- version bump。
- release notes。
- release review。
- tag decision。

## 4. 明确不做（边界）

- 不默认执行真实外网 LLM。
- 不提交 API key/token/client_secret。
- 不接真实外部 MCP 作为默认依赖。
- 不宣称公网生产可直接上线。
- 不宣称多租户/复杂 BI/生产级 SSO 全部完成。

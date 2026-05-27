# 生产就绪检查清单（v3.0.0 release prep / Final Production Landing）

> 目标：用于企业内网试点的准生产可投入使用检查，不等于公网生产上线批准。

## 1. 配置安全

- [ ] `APP_ENV=production`
- [ ] `JWT_SECRET` 已替换默认开发占位值
- [ ] 未提交真实 `.env.production`
- [ ] 未在日志/脚本输出中暴露密钥原文
- [ ] `CORS_ENABLED=true` 且 `CORS_ALLOW_ORIGINS` 为明确来源（非 `*`）
- [ ] `SECURITY_HEADERS_ENABLED=true`
- [ ] `REQUEST_SIZE_LIMIT_ENABLED=true` 且 `REQUEST_SIZE_LIMIT_BYTES` 在合理范围（<=10MB）
- [ ] `RATE_LIMIT_ENABLED=true` 且限流参数有效（`RATE_LIMIT_REQUESTS_PER_MINUTE` > 0，`RATE_LIMIT_BURST` >= 0）
- [ ] `ABUSE_GUARD_ENABLED=true`
- [ ] `STRUCTURED_LOGGING_ENABLED=true`
- [ ] `LOG_REDACTION_ENABLED=true`
- [ ] `LOG_LEVEL` 为 `INFO/WARNING/ERROR/CRITICAL`（production 不允许 `DEBUG`）
- [ ] `AUDIT_RETENTION_ENABLED=true` 且 `AUDIT_RETENTION_DAYS>0`
- [ ] `AUDIT_EXPORT_MAX_ROWS` 在合理范围（1~10000）
- [ ] `AUDIT_EXPORT_REDACTION_ENABLED=true`
- [ ] 如启用 OIDC：`OIDC_ISSUER_URL` / `OIDC_CLIENT_ID` / `OIDC_REDIRECT_URI` 已配置
- [ ] 如启用 OIDC：`OIDC_CLIENT_SECRET_ENV` 指向的环境变量已注入（不提交明文）
- [ ] production + OIDC 启用时：`OIDC_REQUIRE_HTTPS=true` 且 issuer/redirect 使用 https
- [ ] `OIDC_DEFAULT_ROLE` 在 `OIDC_ALLOWED_ROLES` 内，且角色仅限 admin/operator/viewer/auditor

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
- [ ] 响应头包含 `X-Request-ID`，可用于链路排查
- [ ] `/audit/events/export` 可导出 JSONL，且仅输出白名单字段 + 脱敏 detail

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
- [ ] 完整公网生产安全基线（当前已完成 Phase 7.1/7.2/7.3/7.4/7.5：CORS、安全响应头、request size limit、rate limit、basic abuse guard、结构化日志脱敏、审计留存与导出边界、OIDC 最小接入骨架与配置预检）
- [ ] 多实例一致性限流（当前仅进程内内存限流）

## 11. v2.8 Controlled Real LLM Pilot 验收检查

- [ ] 默认 `REAL_LLM_ACCEPTANCE_ENABLED=false`、`REAL_LLM_PREFLIGHT_ENABLED=false`、`REAL_LLM_SMOKE_ENABLED=false`
- [ ] `/llm/preflight` 返回结构化字段，且不泄漏 API key 原文
- [ ] `network_check=true` 仅在显式开关和配置完整时执行
- [ ] acceptance_summary 包含 request_id/fallback_reason/budget_action/cache_hit/cost
- [ ] 审计导出不包含 prompt 原文与密钥原文
- [ ] 真实 LLM smoke 报告已归档（opt-in）
- [ ] 未宣称真实 LLM 生产验收完成

## 12. v2.9.0 release prep 补充检查

- [ ] 当前后端全量基线为 750 passed, 4 skipped（若再次全量验证变化，以最新结果为准）
- [ ] `/llm/preflight` 在默认关闭语义下返回 `status=disabled` 且不阻断默认离线路径
- [ ] 前端 `/llm` 页面仅展示状态观测信息，不提供密钥输入与明文展示
- [ ] acceptance_summary 字段完整（provider/model/fallback/budget/cache/cost/request_id/error_type）
- [ ] 审计导出继续保持白名单 + 脱敏，不导出 prompt 原文与密钥原文
- [ ] 真实 LLM smoke 仍为 opt-in，本轮 release prep 未执行真实外网 LLM smoke
- [ ] 不宣称真实 LLM 生产验收完成，不宣称公网生产可直接上线

## 13. v2.8 发布后收口与 v2.9 入口

- [ ] v2.8.0 GitHub Release 已手动创建并记录（tag 不移动）
- [ ] 下一阶段进入 v2.9 Real LLM Controlled Pilot Evidence 规划与实施

## 14. v2.9 Phase 9.1~9.4 交付检查

- [ ] 已实现统一试点报告模型（PilotReportSummary / PilotReportCase / PilotReportArtifact）
- [ ] 已实现 JSON 与 Markdown 报告写入器，默认目录 `docs/reports/real_llm_pilot/`
- [ ] 报告默认脱敏：不包含 prompt 原文与密钥原文
- [ ] 默认不执行真实 LLM，默认 pytest/CI 不调用真实 LLM
- [ ] 已完成 Phase 9.2：opt-in smoke（NL2SQL/Judge）自动生成脱敏报告
- [ ] 可通过 `REAL_LLM_PILOT_REPORT_DIR` 覆盖报告输出目录
- [ ] 已完成 Phase 9.3：NL2SQL/Judge/audit/metrics 证据串联（evidence_links + observability）
- [ ] evidence_links 与 metrics snapshot 仅保留脱敏摘要，不包含 prompt 原文与密钥原文
- [ ] Judge evidence_links 必须可追溯（`llm_judge_acceptance`）或明确标记未记录（非空语义说明）
- [ ] 已完成 Phase 9.4：pilot evidence 只读 API / 前端入口（只读、脱敏、不触发真实 LLM）

## 15. v2.9 发布完成与 v3.0 入口

- [ ] v2.9.0 GitHub Release 已手动创建并记录（tag 不移动）
- [ ] 下一阶段进入 v3.0 Final Production Landing 规划与实施
- [ ] 已建立 v3.0 规划文档：`docs/v3_final_production_landing_plan.md`

## 16. v3.0 Phase 10.1（真实 LLM 受控试点实测报告归档）检查

- [ ] 已建立执行记录模板：`docs/real_llm_pilot_execution_log_v30.md`
- [ ] 仅在显式 opt-in 环境变量齐全时执行真实 LLM smoke
- [ ] 环境不齐全时记录 skipped，不伪造成功报告
- [ ] 不提交 API key/token/client_secret，不记录 prompt 原文
- [ ] 默认 fake/offline 与默认 pytest/CI 行为保持不变

## 17. v3.0 Phase 10.2（生产部署演练与回滚）检查

- [ ] 已建立演练记录文档：`docs/production_deployment_drill_v30.md`
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` 缺变量按预期失败
- [ ] 注入临时合法 `JWT_SECRET`/`DATABASE_URL`/`REDIS_URL` 后 prod compose config 通过
- [ ] `scripts/prod_config_check.ps1` 在 development 为通过或 warning 通过
- [ ] `scripts/prod_config_check.ps1` 在 production 缺配置时失败
- [ ] `scripts/prod_config_check.ps1` 在 production 临时合法配置时通过
- [ ] 回滚步骤明确：停止 prod compose、恢复默认 compose、清理临时环境变量、不删用户数据

## 18. v3.0 Phase 10.3（运维监控与备份恢复演练）检查

- [ ] 已建立运维演练文档：`docs/operations_monitoring_backup_drill_v30.md`
- [ ] runbook 覆盖 `/health`、`/deployment/check`、`/metrics/runtime`、`/llm/pilot/reports`、`/audit/events/export`
- [ ] 结构化日志与 `X-Request-ID` 链路检查项已记录
- [ ] SQLite 备份恢复模板已记录（停服务复制/替换文件）
- [ ] PostgreSQL 备份恢复模板已记录（`pg_dump` / `psql`，不含真实连接串）
- [ ] Redis 备份恢复模板已记录（RDB/AOF 或 `redis-cli --rdb`，不含真实密码）
- [ ] audit export / pilot report export 保持脱敏边界，不导出 prompt 原文与密钥原文
- [ ] 清理前先备份，不删除用户数据
- [ ] 本轮验证结果已记录（可执行命令 + executed/skipped）

## 19. v3.0 Phase 10.4（安全复核与 Go/No-Go）检查

- [ ] 已建立安全复核文档：`docs/security_go_no_go_review_v30.md`
- [ ] deployment guard 复核覆盖 JWT_SECRET / DATABASE_URL / REDIS_URL / CORS / 安全响应头 / rate limit / audit retention / OIDC
- [ ] HTTP 安全基线复核覆盖 CORS、安全响应头、request size limit、rate limit、basic abuse guard
- [ ] 结构化日志与 `X-Request-ID` 链路复核通过，日志脱敏边界明确
- [ ] audit export 白名单 + redaction required + JSONL 导出边界复核通过
- [ ] LLM 边界复核覆盖 preflight disabled 语义、opt-in smoke、pilot report 脱敏、pilot reports 只读 API path traversal 防护
- [ ] OIDC 当前边界复核：最小接入骨架 + 配置预检 + 默认关闭
- [ ] 已链接 Phase 10.2 / 10.3 演练文档
- [ ] Go/No-Go 结论已收口：企业内网试点/准生产演示 Go，公网生产直上 No-Go

## 20. v3.0.0 release prep 收口检查

- [ ] 版本号已同步到 3.0.0（pyproject / app.version / health.version / stdio fallback / tests 断言）
- [ ] 已新增 `RELEASE_NOTES_v3.0.0.md`
- [ ] 已新增 `docs/release_review_v3.0_final_production_landing.md`
- [ ] release notes 覆盖 Phase 10.1~10.4 与边界声明
- [ ] release review 覆盖 scope / changed modules / verification matrix / security & operational boundary / known limitations / Go-No-Go
- [ ] 默认 fake/offline 与默认 pytest/CI 不调用真实 LLM 行为保持不变
- [ ] 本轮未执行真实外网 LLM

## 21. v3.1 Productization Enhancement 规划入口

- [ ] 已建立 v3.1 规划文档：`docs/v3_1_productization_enhancement_plan.md`
- [ ] v3.0.0 GitHub Release 已完成并记录，`v3.0.0` tag 保持不变
- [ ] v3.1 不改当前发布版本号（当前仍为 3.0.0）
- [ ] v3.1 仍保持默认 fake/offline，默认 pytest/CI 不调用真实 LLM
- [ ] v3.1 仍保持边界：不宣称公网生产直上、不宣称真实 LLM 生产验收完成、不宣称生产级 SSO/OIDC/多租户/复杂 BI 全量完成

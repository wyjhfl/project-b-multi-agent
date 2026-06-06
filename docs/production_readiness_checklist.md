# 生产就绪检查清单（v3.4.0 release prep / Pilot Hardening & Operator Experience）

## 67. v3.7 Phase 17.4 Store and Redis production readiness drill 检查（当前已完成）

- [x] 已新增 runbook：`docs/store_redis_readiness_drill_v37.md`。
- [x] 已新增只读演练脚本：`scripts/store_redis_readiness_drill.py`。
- [x] 已新增测试：`tests/test_store_redis_readiness_drill_v374.py`。
- [x] 默认输出目录：`docs/reports/store_redis_readiness_drill/`。
- [x] 覆盖 PostgreSQL Store opt-in、Store Factory、SQLite fallback、Alembic migration precheck、Redis opt-in、NoopRedisClient fallback、进程内限流边界、deployment guard、审计/指标 store 边界和 compose readiness。
- [x] 输出明确 `database_connected=false`、`redis_connected=false`、`migration_executed=false`、`business_data_written=false`、`audit_data_written=false`、`metrics_data_written=false`。
- [x] 不连接真实 PostgreSQL，不连接真实 Redis，不执行 Alembic migration，不写业务/审计/指标数据。
- [x] 不读取或输出 `DATABASE_URL`、`REDIS_URL`、`JWT_SECRET` 等 secret 原文。
- [x] 缺少 PostgreSQL/Redis opt-in 条件时记录为 `skipped`，不伪造成 `success`。
- [x] 不宣称 PostgreSQL、Redis 或多实例限流生产验收完成；下一建议阶段为 Phase 17.5 Business system integration safety checklist。

## 68. v3.7 Phase 17.5 Business system integration safety checklist 检查（当前已完成）

- [x] 已新增 runbook：`docs/business_system_integration_safety_checklist_v37.md`。
- [x] 已新增只读安全清单脚本：`scripts/business_system_integration_safety_checklist.py`。
- [x] 已新增测试：`tests/test_business_system_integration_safety_checklist_v375.py`。
- [x] 默认输出目录：`docs/reports/business_system_integration_safety/`。
- [x] 覆盖业务系统 opt-in、secret target、ToolGateway/PolicyEngine/OperationWhitelist、allowlist 与超时、写入边界、审批恢复、审计证据、request/prompt safety、回滚与失败恢复证据。
- [x] 输出明确 `business_system_connected=false`、`business_read_executed=false`、`business_write_executed=false`、`business_data_written=false`、`approval_bypassed=false`、`audit_bypassed=false`。
- [x] 不连接真实业务系统，不执行真实读写，不创建/更新/删除业务数据。
- [x] 不绕过 ToolGateway、PolicyEngine、审批链路或审计链路。
- [x] 不读取或输出 token、API key、client_secret、连接串密码或业务系统 URL 原文。
- [x] 缺少写入 allowlist、审批、审计、回滚或失败恢复证据时记录为 `skipped`，不伪造成 `success`。
- [x] 不宣称真实业务系统生产集成验收完成；下一建议阶段为 Phase 17.6 v3.7 release prep。

## 69. v3.7.0 release prep 检查（当前已完成）

- [x] 版本号已同步到 `3.7.0`（pyproject / FastAPI version / `/health.version` / MCP stdio fallback / v3.7 script version markers / related tests）。
- [x] 已新增 `RELEASE_NOTES_v3.7.0.md`。
- [x] 已新增 `docs/release_review_v3.7_external_integration_real_provider_acceptance.md`。
- [x] release notes 覆盖 Phase 17.1~17.5、状态语义与默认 fake/offline 约束。
- [x] release review 覆盖 scope、changed docs/scripts/tests/modules、verification matrix、security/privacy boundary、operational boundary、known limitations、Go/No-Go。
- [x] 本轮 release prep 不打 tag、不创建 GitHub Release、不移动历史 tag。
- [x] 默认 fake/offline 与默认 pytest/CI 不调用真实 LLM 边界保持明确。
- [x] 本轮不连接真实外部 MCP、真实业务系统、真实 PostgreSQL、真实 Redis 或真实 IdP。
- [x] 不宣称公网生产可直接上线，不宣称真实 LLM/MCP/PostgreSQL/Redis/业务系统生产验收完成。
- [x] 全量回归 `python -m pytest -q`：880 passed, 4 skipped, 2 warnings。
- [x] `docker compose config` 与 prod override config 通过，仅 Docker config 读权限 warning。
- [x] `git diff --check` 通过，仅 CRLF 转换提示。

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

- [ ] 当前后端全量基线为 831 passed, 4 skipped（若再次全量验证变化，以最新结果为准）
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
- [ ] v3.1.0 历史 release prep 已完成并发布
- [ ] v3.1 仍保持默认 fake/offline，默认 pytest/CI 不调用真实 LLM
- [ ] v3.1 仍保持边界：不宣称公网生产直上、不宣称真实 LLM 生产验收完成、不宣称生产级 SSO/OIDC/多租户/复杂 BI 全量完成

## 22. v3.1 Phase 11.1（演示数据与端到端演示脚本）检查

- [ ] 已新增离线 seed 脚本：`scripts/demo_seed_data.py`
- [ ] 已新增 E2E 演示脚本：`scripts/demo_e2e.ps1`
- [ ] 已新增 runbook：`docs/demo_e2e_runbook_v31.md`
- [ ] seed 数据覆盖任务/审批/审计/metrics/NL2SQL/pilot report/trace 示例
- [ ] 脚本默认 fake/offline，不调用真实外网 LLM，不依赖真实外部 MCP
- [ ] 服务未启动时在线 smoke 明确 `status=skipped`，不误报成功
- [ ] 本阶段不改版本号、不打 tag、不创建 Release

## 23. v3.1 Phase 11.2（只读运营总览 Dashboard）检查

- [ ] 已新增只读运营总览后端接口：`GET /operations/summary`
- [ ] 已新增前端只读入口：`/operations`
- [ ] 总览覆盖 health/version、deployment、runtime metrics、tasks/approvals、audit、pilot reports/demo evidence 摘要
- [ ] 不提供真实 LLM 调用按钮、不提供密钥输入、不提供写操作/删除操作
- [ ] pilot report 目录不存在时返回空状态，不报 500
- [ ] 汇总响应保持脱敏边界：不返回 prompt 原文、密钥/token/password/DSN 密码
- [ ] 默认 fake/offline 与默认 pytest/CI 不调用真实 LLM 行为保持不变

## 24. v3.1 Phase 11.3（真实 LLM opt-in 实测执行与报告归档）检查

- [ ] 已新增执行记录：`docs/real_llm_pilot_execution_log_v31.md`
- [ ] 仅在 opt-in 必需变量齐全时执行真实外网 LLM smoke
- [ ] 变量缺失时记录 `status=skipped`，不伪造成功报告
- [ ] 若执行成功，归档 JSON/Markdown 报告并记录 request_id/tokens/cost/fallback/budget/cache/evidence links
- [ ] 报告与执行记录不包含 prompt 原文与密钥原文
- [ ] 本阶段不改版本号、不打 tag、不创建 Release、不移动 `v3.0.0` tag

## 25. v3.1 Phase 11.4（OIDC/SSO 最小真实 IdP 配置演练）检查

- [ ] 已新增演练文档：`docs/oidc_minimal_idp_drill_v31.md`
- [ ] 已覆盖配置项：issuer/client_id/client_secret_env/redirect_uri/scopes/role_claim/default_role/allowed_roles/require_https
- [ ] 已明确 development 与 production 差异（localhost http 仅 development warning；production 必须 https）
- [ ] 已覆盖 `/auth/oidc/status` 与 `/deployment/check` 检查步骤
- [ ] 已覆盖常见失败场景与回滚步骤（关闭 OIDC、清理临时 env、不删除用户数据）
- [ ] 不提交真实 client_secret，不接入真实生产 IdP，不宣称生产级 SSO/OIDC 完成

## 26. v3.1 Phase 11.5（运维 polish）检查

- [ ] 已新增运维排障索引：`docs/operations_troubleshooting_index_v31.md`
- [ ] 已新增备份恢复检查清单：`docs/backup_restore_checklist_v31.md`
- [ ] 排障索引已覆盖：服务未启动、compose 配置失败、deployment check `ok=false`、`/operations` 无数据、demo smoke skipped、pilot reports 为空、audit export 403、OIDC secret env 缺失、real LLM opt-in skipped
- [ ] 每个场景均明确“不删除用户数据”恢复原则
- [ ] 备份恢复检查清单已覆盖 sqlite / postgres / redis 模板与恢复后验证命令
- [ ] 文档示例仅使用占位符，不包含真实凭据

## 27. v3.1.0 release prep 收口检查（历史）

- [ ] 版本号已同步到 3.1.0（pyproject / app.version / health.version / stdio fallback / tests 断言）
- [ ] 已新增 `RELEASE_NOTES_v3.1.0.md`
- [ ] 已新增 `docs/release_review_v3.1_productization_enhancement.md`
- [ ] release notes 覆盖 Phase 11.1~11.5 与边界声明
- [ ] release review 覆盖 scope / changed modules / verification matrix / security/privacy boundary / operational boundary / known limitations / Go-No-Go
- [ ] 默认 fake/offline 与默认 pytest/CI 不调用真实 LLM 行为保持不变
- [ ] 本轮未执行真实外网 LLM
- [ ] v3.0.0 tag 与 GitHub Release 已完成且不移动
- [ ] 当前 main 超前 `v3.0.0` tag 属于 v3.1.0 release prep
- [ ] 本轮不打 tag、不创建 GitHub Release

## 28. v3.2 Acceptance & Observability Enhancement 规划入口

- [ ] 已建立 v3.2 规划文档：`docs/v3_2_acceptance_observability_plan.md`
- [ ] v3.1.0 GitHub Release 已完成并记录，`v3.1.0` / `v3.0.0` tag 保持不变
- [ ] 当前版本仍为 `3.1.0`（本阶段不改版本号）
- [ ] v3.2 规划保持默认 fake/offline，默认 pytest/CI 不调用真实 LLM
- [ ] v3.2 规划保持边界：不宣称公网生产直上、不宣称真实 LLM 生产验收完成、不宣称生产级 SSO/OIDC/多租户/复杂 BI 全量完成
- [ ] 推荐优先级：P0（12.1+12.3）、P1（12.2+12.4）、P2（12.5+12.6）

## 29. v3.2 Phase 12.1（Acceptance snapshot 一键生成）检查

- [ ] 已新增脚本：`scripts/acceptance_snapshot.py`
- [ ] 已新增 runbook：`docs/acceptance_snapshot_runbook_v32.md`
- [ ] 默认输出目录：`docs/reports/acceptance_snapshots/`
- [ ] 输出包含 JSON + Markdown
- [ ] 快照覆盖 health/deployment/operations/metrics/audit/pilot reports/demo evidence 摘要
- [ ] 脱敏边界满足：不含 prompt/query/raw_prompt/sql_prompt 原文，不含 key/token/client_secret/password/JWT_SECRET/DATABASE_URL/REDIS_URL 明文
- [ ] 服务未启动时在线检查标记 skipped，不误报 success
- [ ] 默认 fake/offline，不触发真实 LLM，不写业务数据


## 30. v3.2 Phase 12.3 (Demo artifact bundle) checks

- [ ] `scripts/demo_e2e.ps1` supports `-ArtifactDir`, default `docs/reports/demo_artifacts/`
- [ ] each run creates a timestamped artifact subdirectory
- [ ] generates `demo_e2e_summary.json`, `online_smoke_result.json`, `seed_summary.json`
- [ ] generates `pilot_report_index.json` with pilot report dir and total count
- [ ] calls acceptance snapshot and records snapshot json/md paths
- [ ] when service is unavailable, online smoke is skipped without false success
- [ ] output remains sanitized: no prompt/query/raw_prompt/sql_prompt raw text and no secret plaintext

## 31. v3.2 Phase 12.2 (Operations observability polish) checks

- [ ] `/operations` keeps read-only behavior and does not add write/delete actions
- [ ] empty states are explicit: service unavailable / no reports / no audit events / skipped online checks
- [ ] observability metadata is exposed in `/operations/summary` (runbook paths + default dirs + last known counts)
- [ ] UI keeps boundary hints: fake/offline default, no real LLM call, no secret plaintext
- [ ] long path strings can wrap without layout break

## 32. v3.2 Phase 12.4（Failure diagnostics pack）检查

- [ ] 已新增诊断 runbook：`docs/failure_diagnostics_pack_v32.md`
- [ ] 已新增只读诊断脚本：`scripts/failure_diagnostics.py`
- [ ] 默认输出目录：`docs/reports/failure_diagnostics/`（支持 `--output-dir` 覆盖）
- [ ] 输出包含 JSON + Markdown，且不包含 prompt/query/raw_prompt/sql_prompt 原文
- [ ] 输出不包含 key/token/client_secret/password/JWT_SECRET/DATABASE_URL/REDIS_URL 明文
- [ ] 覆盖场景：compose、prod 缺变量、deployment check、operations unavailable、demo/acceptance skipped、pilot reports 为空、audit export 403、OIDC secret env 缺失、real LLM opt-in skipped
- [ ] 服务不可用时标记 skipped，不误报 success
- [ ] 脚本保持只读，不写业务数据、不删除用户数据、不修改环境变量

## 33. v3.2 Phase 12.5（Optional real LLM evidence retry）检查

- [ ] 已新增执行记录：`docs/real_llm_optional_retry_log_v32.md`
- [ ] 仅在 opt-in 必需变量齐全时执行真实外网 LLM
- [ ] 必需变量缺失时记录 `status=skipped`，不伪造成功
- [ ] 本轮如 skipped，必须明确“未生成真实外网 pilot report”
- [ ] 若执行成功，报告仍需保持脱敏边界（不含 prompt 原文/密钥原文/DSN 密码）
- [ ] 不改版本号、不打 tag、不创建 Release、不移动 `v3.1.0` / `v3.0.0` tag

## 34. v3.2.0 release prep 收口检查（历史）

- [ ] 版本号已同步到 3.2.0（pyproject / app.version / health.version / stdio fallback / tests 断言 / snapshot & diagnostics 版本字段）
- [ ] 已新增 `RELEASE_NOTES_v3.2.0.md`
- [ ] 已新增 `docs/release_review_v3.2_acceptance_observability.md`
- [ ] release notes 覆盖 Phase 12.1~12.5 与 cleanup 条目（token metrics 保真、ArtifactDir 目录约束）
- [ ] release review 覆盖 scope / changed modules / verification matrix / security & operational boundary / known limitations / Go-No-Go
- [ ] 默认 fake/offline 与默认 pytest/CI 不调用真实 LLM 行为保持不变
- [ ] 本轮未执行真实外网 LLM
- [ ] `v3.1.0`/`v3.0.0` tag 与对应 GitHub Release 已完成且不移动
- [ ] 当前 main 超前 `v3.1.0` tag 属于 v3.2.0 release prep
- [ ] 本轮不打 `v3.2.0` tag、不创建 v3.2.0 GitHub Release

## 35. v3.3 Operational Automation & Governance 规划入口

- [ ] 已建立 v3.3 规划文档：`docs/v3_3_operational_automation_governance_plan.md`
- [ ] 已记录 `v3.2.0` GitHub Release 已完成，且 `v3.2.0` / `v3.1.0` / `v3.0.0` tag 保持不变
- [ ] 当前版本仍为 `3.2.0`（本阶段不改版本号）
- [ ] v3.3 规划保持默认 fake/offline，默认 pytest/CI 不调用真实 LLM
- [ ] v3.3 规划保持边界：不宣称公网生产直上、不宣称真实 LLM 生产验收完成、不宣称生产级 SSO/OIDC/多租户/复杂 BI 全量完成
- [ ] 推荐优先级：P0（13.1+13.2）、P1（13.3+13.4）、P2（13.5+13.6）

## 36. v3.3 Phase 13.1（Report index & retention）检查

- [ ] 已新增脚本：`scripts/report_index.py`
- [ ] 已新增测试：`tests/test_report_index_v331.py`
- [ ] 已新增 runbook：`docs/report_index_retention_runbook_v33.md`
- [ ] 默认扫描目录：
  - `docs/reports/acceptance_snapshots/`
  - `docs/reports/demo_artifacts/`
  - `docs/reports/failure_diagnostics/`
- [ ] 默认输出目录：`docs/reports/report_index/`，支持 `--output-dir` 覆盖
- [ ] 输出包含 JSON + Markdown，且包含 generated_at/commit/report_type/file_count/latest_path/total_size/stale_candidates/retention_policy
- [ ] stale candidates 仅列出，不删除文件
- [ ] 明确保留策略边界：不删除用户数据、不删除报告、不自动清理

## 37. v3.3 Phase 13.2（Config drift checklist）检查

- [ ] 已新增脚本：`scripts/config_drift_check.py`
- [ ] 已新增测试：`tests/test_config_drift_v332.py`
- [ ] 已新增清单文档：`docs/config_drift_checklist_v33.md`
- [ ] 默认输出目录：`docs/reports/config_drift/`，支持 `--output-dir` 覆盖
- [ ] 输出包含 JSON + Markdown，且包含 generated_at/commit/checked_files/missing_in_example/missing_in_production_example/deployment_guard_related/oidc_related/audit_related/real_llm_related/compose_required_env/warnings/boundary_declarations
- [ ] 只读边界：不修改 `.env` 模板、不读取真实密钥值、不输出密钥明文

## 38. v3.3 Phase 13.3（Governance policy summary）检查

- [ ] 已新增脚本：`scripts/governance_policy_summary.py`
- [ ] 已新增测试：`tests/test_governance_policy_summary_v333.py`
- [ ] 已新增治理摘要文档：`docs/governance_policy_summary_v33.md`
- [ ] 默认输出目录：`docs/reports/governance_policy/`，支持 `--output-dir` 覆盖
- [ ] 治理摘要覆盖 default fake/offline、pytest/CI 默认不调用真实 LLM、real LLM opt-in 缺变量 skipped、secret/redaction/OIDC/report retention/config drift/release-tag 边界
- [ ] 只读边界：不写业务数据、不读取真实密钥、不改业务逻辑、不改版本号、不打 tag、不创建 Release、不执行真实外网 LLM

## 39. v3.3 Phase 13.4（Operations automation script polish）检查

- [ ] 已新增统一文档：`docs/operations_automation_scripts_v33.md`
- [ ] 已新增一致性测试：`tests/test_operations_automation_scripts_v334.py`
- [ ] 已统一 acceptance/demo artifact/failure diagnostics/report index/config drift/governance 脚本 summary 元字段
- [ ] 保持只读边界：不删除用户数据、不自动清理报告、不修改 `.env`、不读取/输出真实 secret、不执行真实外网 LLM
- [ ] 不改版本号、不打 tag、不创建 Release、不移动 `v3.2.0/v3.1.0/v3.0.0` tag

## 40. v3.3 Phase 13.5 (Optional live drill window) checks

- [ ] Added runbook: `docs/live_drill_window_v33.md`
- [ ] Added read-only precheck script: `scripts/live_drill_window.py`
- [ ] Added test: `tests/test_live_drill_window_v335.py`
- [ ] Service window checks cover `/health`, `/deployment/check`, `/operations/summary`
- [ ] Readiness checks cover acceptance snapshot / demo artifact bundle / failure diagnostics / config drift / governance summary
- [ ] Real LLM remains opt-in only; missing required env must be recorded as `skipped` with missing list
- [ ] OIDC live drill readiness checks are recorded without exposing secret values
- [ ] Boundary declarations remain explicit: not public production launch approval, not real LLM production acceptance completion, not production-grade SSO/OIDC completion

## 41. v3.3.0 release prep closure checks (current)

- [ ] Version synchronized to 3.3.0 (`pyproject`, FastAPI version, `/health.version`, MCP stdio fallback, script version markers, related tests).
- [ ] Added `RELEASE_NOTES_v3.3.0.md`.
- [ ] Added `docs/release_review_v3.3_operational_automation_governance.md`.
- [ ] Release notes cover Phase 13.1~13.5 and live drill skipped-logic fix.
- [ ] Release review covers scope / changed modules / verification matrix / boundaries / limitations / Go-No-Go.
- [ ] Default fake/offline and pytest/CI no-real-LLM boundary remains explicit.
- [ ] Phase 13.5 this round does not execute real external LLM.
- [ ] No v3.3.0 tag is created in this round.
- [ ] No v3.3.0 GitHub Release is created in this round.

## 42. v3.4 规划入口检查（历史）

- [ ] 已创建规划文档：`docs/v3_4_pilot_hardening_operator_experience_plan.md`。
- [ ] v3.4 定位为 Pilot Hardening & Operator Experience。
- [ ] 版本已在 v3.4.0 release prep 阶段同步为 `3.4.0`。
- [ ] `v3.3.0` GitHub Release 已完成，历史 tags 保持不变。
- [ ] 规划轮次保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，默认不执行真实外网 LLM。
- [ ] 本轮不改业务逻辑、不改版本号、不打 tag、不创建 Release。
- [ ] 不宣称公网生产直上，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 或多租户/复杂 BI 全量完成。
## 43. v3.4 Phase 14.1 操作员工作流收口检查（已完成）

- [ ] 已新增操作员工作流文档：`docs/operator_workflow_polish_v34.md`。
- [ ] 已新增只读索引脚本：`scripts/operator_workflow_index.py`。
- [ ] 已新增测试：`tests/test_operator_workflow_index_v341.py`。
- [ ] 默认输出目录：`docs/reports/operator_workflow/`。
- [ ] 入口覆盖 `/operations`、acceptance snapshot、demo artifact bundle、failure diagnostics、report index、config drift、governance summary、live drill window。
- [ ] 每个入口说明使用时机、默认输出目录、是否只读、是否调用真实 LLM、失败或 skipped 状态解释。
- [ ] 保持只读边界：不删除数据、不自动清理报告、不修改 `.env`、不读取或输出真实 secret 原文、不执行真实外网 LLM。
- [ ] 本阶段不改业务逻辑、不改版本号、不打 tag、不创建 Release。

## 44. v3.4 Phase 14.2 故障演练包检查（已完成）

- [ ] 已新增故障演练文档：`docs/incident_rehearsal_pack_v34.md`。
- [ ] 已新增只读演练脚本：`scripts/incident_rehearsal_pack.py`。
- [ ] 已新增测试：`tests/test_incident_rehearsal_pack_v342.py`。
- [ ] 默认输出目录：`docs/reports/incident_rehearsal/`。
- [ ] 覆盖 service unavailable、docker compose config failure、prod compose missing required env、deployment check ok=false、operations unavailable/empty、acceptance/demo skipped、failure diagnostics blocked、report index empty/stale、config drift warnings、governance/live drill skipped、OIDC secret env missing、real LLM opt-in missing/skipped。
- [ ] 输出字段覆盖 `generated_at`、`commit`、`version`、`mode`、`read_only`、`real_llm_executed`、`scenarios`、`recommended_runbooks`、`missing_conditions`、`status`、`boundary_declarations`、`output_dir`。
- [ ] 状态词限定为 `success / skipped / blocked / partial / failed`。
- [ ] 默认不启动服务、不修改环境、不执行真实外网 LLM；缺少 opt-in 条件必须 `skipped`。

## 45. v3.4 Phase 14.3 证据归档 Manifest 检查（已完成）

- [ ] 已新增证据归档文档：`docs/evidence_archive_manifest_v34.md`。
- [ ] 已新增只读 manifest 脚本：`scripts/evidence_archive_manifest.py`。
- [ ] 已新增测试：`tests/test_evidence_archive_manifest_v343.py`。
- [ ] 默认输出目录：`docs/reports/evidence_archive/`。
- [ ] 纳入 acceptance snapshots、demo artifacts、failure diagnostics、report index、config drift、governance policy、live drill window、operator workflow、incident rehearsal、release review / post release handoff 文档。
- [ ] 输出字段覆盖 `generated_at`、`commit`、`version`、`manifest_id`、`evidence_roots`、`evidence_items`、`latest_by_type`、`missing_expected_types`、`total_files`、`total_size_bytes`、`retention_policy`、`boundary_declarations`、`read_only`、`real_llm_executed`。
- [ ] 只读索引：不删除文件、不读取报告内容、不输出 secret 原文、不自动执行 retention 清理。
- [ ] 空目录或缺失目录以 `skipped` 或 `warning` 表示，不伪造成成功。

## 46. v3.4 Phase 14.4 可选集成准备度矩阵检查（已完成）

- [ ] 已新增准备度矩阵文档：`docs/optional_integration_readiness_matrix_v34.md`。
- [ ] 已新增只读矩阵脚本：`scripts/optional_integration_readiness.py`。
- [ ] 已新增测试：`tests/test_optional_integration_readiness_v344.py`。
- [ ] 默认输出目录：`docs/reports/optional_integration_readiness/`。
- [ ] 覆盖 real LLM、OIDC、external MCP、Postgres、Redis、frontend build/network dependency、deployment guard、audit export/redaction readiness。
- [ ] 输出字段覆盖 `generated_at`、`commit`、`version`、`integrations`、`readiness_status`、`missing_conditions`、`skipped_reasons`、`risk_notes`、`recommended_next_actions`、`boundary_declarations`、`read_only`、`real_llm_executed`。
- [ ] 仅检查配置存在性和本地可验证条件，不读取真实 secret 值，仅输出 env name 与 `present=true/false`。
- [ ] 不调用真实外网 LLM，不连接真实外部 MCP；缺少真实 opt-in 条件必须 `skipped`。

## 47. v3.4 Phase 14.5 企业内网试点交接清单检查（已完成）

- [ ] 已新增交接文档：`docs/pilot_handoff_checklist_v34.md`。
- [ ] 已新增只读生成脚本：`scripts/pilot_handoff_checklist.py`。
- [ ] 已新增测试：`tests/test_pilot_handoff_checklist_v345.py`。
- [ ] 默认输出目录：`docs/reports/pilot_handoff/`。
- [ ] 覆盖 admin/operator/viewer/auditor、RBAC 边界、OIDC 最小演练边界、real LLM opt-in skipped/ready 解释。
- [ ] 引用 incident rehearsal、evidence archive manifest、optional integration readiness、backup/restore/checklist 链接。
- [ ] Go/No-Go 明确：企业内网试点可继续，公网直上 No-Go，真实生产验收需另行执行。
- [ ] 保持只读边界：不读取 secret 原文、不执行真实外网 LLM、不写业务数据。

## 48. v3.4.0 release prep 收口检查（历史）

- [ ] 版本号已同步到 3.4.0（pyproject / FastAPI version / `/health.version` / MCP stdio fallback / script version markers / related tests）。
- [ ] 已新增 `RELEASE_NOTES_v3.4.0.md`。
- [ ] 已新增 `docs/release_review_v3.4_pilot_hardening_operator_experience.md`。
- [ ] release notes 覆盖 Phase 14.1~14.5 与 skipped/blocked/partial 状态边界。
- [ ] release review 覆盖 scope / changed docs/scripts/tests/modules / verification matrix / security/privacy boundary / operational boundary / known limitations / Go-No-Go。
- [ ] 默认 fake/offline 与 pytest/CI 默认不调用真实 LLM 边界保持明确。
- [ ] 本轮不执行真实外网 LLM。
- [ ] 本轮不打 `v3.4.0` tag、不创建 GitHub Release、不移动历史 tag。
- [ ] 可进入 v3.4.0 tag 前最终复核。

## 49. v3.5 规划入口检查（当前）

- [ ] 已创建规划文档：`docs/v3_5_controlled_pilot_expansion_plan.md`。
- [ ] 已创建生产级后续路线图：`docs/enterprise_production_landing_roadmap.md`。
- [ ] v3.5 定位为 Controlled Pilot Expansion & Evidence Operations。
- [ ] 规划覆盖 Phase 15.1~15.6：
  - Phase 15.1 Pilot evidence comparison snapshot。
  - Phase 15.2 Operator drill scoring rubric。
  - Phase 15.3 Controlled integration dry-run checklist。
  - Phase 15.4 Governance exception register。
  - Phase 15.5 Pilot closeout report pack。
  - Phase 15.6 v3.5 release prep。
- [ ] 当前 release prep 阶段版本已同步为 `3.5.0`。
- [ ] `v3.4.0` GitHub Release 已完成，历史 tags 保持不变。
- [ ] 规划轮次保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，默认不执行真实外网 LLM。
- [ ] 本轮不改业务逻辑、不改版本号、不打 tag、不创建 Release。
- [ ] 不读取或输出真实 secret 原文。
- [ ] 不宣称公网生产直上，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 或多租户/复杂 BI 全量完成。

## 50. v3.5 Phase 15.1 试点证据对比快照检查（已完成）

- [ ] 已新增 runbook：`docs/pilot_evidence_comparison_v35.md`。
- [ ] 已新增只读对比脚本：`scripts/pilot_evidence_comparison.py`。
- [ ] 已新增测试：`tests/test_pilot_evidence_comparison_v351.py`。
- [ ] 默认输出目录：`docs/reports/pilot_evidence_comparison/`。
- [ ] 支持 baseline/current manifest JSON 或证据目录输入。
- [ ] 输入为 manifest JSON 时仅读取 `evidence_items` 元数据；输入为目录时仅枚举文件元数据。
- [ ] 输出 JSON + Markdown，覆盖新增、减少、变化文件统计与 `warnings`。
- [ ] 缺失或空输入必须 `skipped` 并记录 `warnings`，不得伪造成成功。
- [ ] 保持只读边界：不删除、不移动、不修改输入证据，不自动执行 retention 清理，不读取或输出真实 secret 原文，不执行真实外网 LLM。
- [ ] Phase 15.1 当轮版本保持 `3.4.0`；v3.5 release prep 已另行同步到 `3.5.0`。

## 51. v3.5 Phase 15.2 操作员演练评分 Rubric 检查（已完成）

- [ ] 已新增 runbook：`docs/operator_drill_scoring_rubric_v35.md`。
- [ ] 已新增只读评分脚本：`scripts/operator_drill_scoring.py`。
- [ ] 已新增测试：`tests/test_operator_drill_scoring_v352.py`。
- [ ] 默认输出目录：`docs/reports/operator_drill_scoring/`。
- [ ] CLI 支持 `--output-dir`、`--incident-report`、`--handoff-report`、`--integration-readiness`、`--evidence-comparison`。
- [ ] 评分维度覆盖 availability、recoverability、evidence_integrity、configuration_readiness、permission_boundary、known_limitations。
- [ ] 输入来源仅消费 incident rehearsal、pilot handoff、optional integration readiness、evidence comparison 的 JSON 元数据。
- [ ] 缺失输入或所有输入为空必须 `skipped`，来源报告 skipped 必须保留 skipped 语义，不得伪造成成功。
- [ ] 不自动改变 Go/No-Go 结论，不读取报告正文，不写业务数据，不读取或输出真实 secret 原文，不执行真实外网 LLM。
- [ ] Phase 15.2 当轮版本保持 `3.4.0`；v3.5 release prep 已另行同步到 `3.5.0`。

## 52. v3.5 Phase 15.3 受控集成 dry-run checklist 检查（已完成）

- [ ] 已新增 runbook：`docs/controlled_integration_dry_run_v35.md`。
- [ ] 已新增只读 dry-run 脚本：`scripts/controlled_integration_dry_run.py`。
- [ ] 已新增测试：`tests/test_controlled_integration_dry_run_v353.py`。
- [ ] 默认输出目录：`docs/reports/controlled_integration_dry_run/`。
- [ ] CLI 支持 `--output-dir`、`--readiness-report`。
- [ ] 覆盖 real LLM、OIDC、external MCP、Postgres、Redis、frontend build/network、deployment guard、audit export redaction。
- [ ] 仅输出 env name 与 `present=true/false`，不输出真实 secret 值。
- [ ] 支持串联 Phase 14.4 optional integration readiness JSON，但只消费结构化元数据。
- [ ] 缺少 opt-in 条件必须 `skipped` 并记录 `missing_conditions`，不得伪造成 `ready/success`。
- [ ] 不启动服务、不修改 `.env`、不连接真实外部 MCP、不调用真实外网 LLM、不读取或输出真实 secret 原文。
- [ ] Phase 15.3 当轮版本保持 `3.4.0`；v3.5 release prep 已另行同步到 `3.5.0`。

## 53. v3.5 Phase 15.4 治理例外登记检查（已完成）

- [ ] 已新增 runbook：`docs/governance_exception_register_v35.md`。
- [ ] 已新增只读治理例外登记脚本：`scripts/governance_exception_register.py`。
- [ ] 已新增测试：`tests/test_governance_exception_register_v354.py`。
- [ ] 默认输出目录：`docs/reports/governance_exceptions/`。
- [ ] CLI 支持 `--output-dir`、`--config-drift`、`--governance-policy`、`--incident-report`、`--operator-scoring`、`--controlled-integration`。
- [ ] 例外字段覆盖风险描述、影响范围、责任人、到期时间、补偿控制、复核证据、状态和下一步动作。
- [ ] 支持引用 config drift、governance policy summary、incident rehearsal、operator drill scoring 的 JSON 元数据。
- [ ] 不自动批准例外，不绕过 deployment guard、安全响应头、审计脱敏或审批链路。
- [ ] 不记录真实 secret 原文，不执行真实外网 LLM，不改版本号，不打 tag，不创建 Release。
- [ ] 输出必须声明不代表生产安全豁免，也不代表公网生产可直接上线。
- [ ] Phase 15.4 当轮版本保持 `3.4.0`；v3.5 release prep 已另行同步到 `3.5.0`。

## 54. v3.5 Phase 15.5 试点收口报告包检查（已完成）

- [x] 已新增 runbook：`docs/pilot_closeout_report_pack_v35.md`。
- [x] 已新增只读收口报告脚本：`scripts/pilot_closeout_report_pack.py`。
- [x] 已新增测试：`tests/test_pilot_closeout_report_pack_v355.py`。
- [x] 默认输出目录：`docs/reports/pilot_closeout/`。
- [x] CLI 支持 `--output-dir`、`--pilot-handoff`、`--evidence-archive`、`--integration-readiness`、`--operator-scoring`、`--controlled-integration`、`--governance-exceptions`。
- [x] 报告包包含 executive summary、evidence summary、known limitations、Go/No-Go、next actions 和 boundary declarations。
- [x] 仅汇总 JSON 元数据，不读取报告正文，不写业务数据。
- [x] 对所有 `skipped/blocked/partial` 项保持原始解释，不做假通过。
- [x] Phase 15.5 交付当轮不改版本号、不打 tag、不创建 Release、不执行真实外网 LLM、不输出真实 secret 原文。
- [x] 输出必须声明不代表生产安全豁免，不代表真实生产验收完成，也不代表公网生产可直接上线。
- [x] 当前版本已完成 `v3.5.0` 发布，发布后收口记录见 `docs/post_release_check_v3.5.0.md`。

## 55. v3.5.0 release-created 收口检查（当前）

- [x] 版本号已同步到 `3.5.0`（pyproject / FastAPI version / `/health.version` / MCP stdio fallback / script version markers / related tests）。
- [x] 已新增 `RELEASE_NOTES_v3.5.0.md`。
- [x] 已新增 `docs/release_review_v3.5_controlled_pilot_expansion.md`。
- [x] 已新增 `docs/post_release_check_v3.5.0.md`。
- [x] release notes 覆盖 Phase 15.1~15.5、状态边界与默认 fake/offline 约束。
- [x] release review 覆盖 scope、changed docs/scripts/tests/modules、verification matrix、security/privacy boundary、operational boundary、known limitations、Go/No-Go。
- [x] GitHub Release `v3.5.0` 已创建，Release notes 来源为 `RELEASE_NOTES_v3.5.0.md`。
- [x] 远端 tag `v3.5.0` 指向 commit `90cf1b3a325032b6d865c82d11035c27cfee3017`。
- [x] 历史 tag 未移动、未删除、未重建。
- [x] 默认 fake/offline 与 pytest/CI 默认不调用真实 LLM 边界保持明确。
- [x] 本轮 release-created 收口不执行真实外网 LLM。
- [x] main 超前 `v3.5.0` tag 属于发布后文档收口。

## 56. v3.6 Enterprise Identity & Tenant Boundary 规划入口检查（当前）

- [x] 已新增规划文档：`docs/v3_6_enterprise_identity_tenant_boundary_plan.md`。
- [x] v3.6 定位为 Enterprise Identity & Tenant Boundary。
- [x] 当前已进入 release prep，版本已同步为 `3.6.0`。
- [x] release prep 阶段不打 tag、不创建 Release、不移动历史 tag。
- [x] `v3.5.0` GitHub Release 已创建，历史 tag 不移动、不删除、不重建。
- [x] 已记录现有身份/RBAC/OIDC 能力：JWT、`/auth/login`、`/auth/me`、`require_permission`、OIDC 配置预检。
- [x] 已记录当前缺口：JWT payload 未包含 tenant/org/project scope，用户模型未包含组织或租户归属，尚无 tenant/org/project/resource ownership 运行时 enforcement。
- [x] 明确默认不启用 `AUTH_ENABLED`、`RBAC_ENABLED`、`OIDC_ENABLED`。
- [x] 明确默认不连接真实外部 IdP，不执行真实 token exchange。
- [x] 明确不输出真实 secret 原文，不宣称生产级 SSO/OIDC 或多租户完成。
- [x] Phase 16.1~16.6 已完成；下一建议阶段为 v3.6.0 tag 前最终复核。

## 57. v3.6 Phase 16.1 身份与租户边界盘点检查（已完成）

- [x] 已新增 runbook：`docs/identity_tenant_boundary_inventory_v36.md`。
- [x] 已新增只读盘点脚本：`scripts/identity_tenant_boundary_inventory.py`。
- [x] 已新增测试：`tests/test_identity_tenant_boundary_inventory_v361.py`。
- [x] 默认输出目录：`docs/reports/identity_tenant_boundary/`。
- [x] 输出当前身份模型、角色层级、权限矩阵、OIDC 配置预检、审计边界和资源归属缺口。
- [x] 缺失 tenant/org/project/resource ownership 时记录为 `gap`，不得伪造成已完成。
- [x] 输出明确 `read_only=true`、`real_idp_connected=false`、`tenant_enforcement_enabled=false`。
- [x] 不读取 `.env` 或真实 secret 值，不连接真实 IdP，不执行 OIDC token exchange。
- [x] 不改 JWT payload，不新增 tenant enforcement，不默认启用 `AUTH_ENABLED`、`RBAC_ENABLED`、`OIDC_ENABLED`。
- [x] 不宣称生产级 SSO/OIDC 或多租户完成。

## 58. v3.6 Phase 16.2 租户归属模型草案检查（已完成）

- [x] 已新增模型设计文档：`docs/tenant_ownership_model_v36.md`。
- [x] 已新增 Pydantic 草案模型：`OrganizationScopeDraft`、`TenantScopeDraft`、`ProjectScopeDraft`、`PrincipalScopeDraft`、`RoleAssignmentDraft`、`ResourceScopeDraft`、`AuditScopeDraft`、`TenantOwnershipModelDraft`。
- [x] 已新增测试：`tests/test_tenant_ownership_model_v362.py`。
- [x] 已定义 `organization`、`tenant`、`project`、`principal`、`role_assignment`、`resource_scope`、`audit_scope` 概念边界。
- [x] 已明确未来可进入 JWT 的 claim 草案：`organization_id`、`tenant_id`、`project_id`。
- [x] 已明确服务端 store 字段、审计字段、跨租户拒绝规则和迁移兼容策略。
- [x] 本阶段不迁移数据库、不改 user store、不改 JWT payload、不启用 tenant enforcement、不改变默认离线 demo。
- [x] 不宣称生产级 SSO/OIDC 或多租户完成。

## 59. v3.6 Phase 16.3 RBAC 权限矩阵强化检查（已完成）

- [x] 已新增 runbook：`docs/rbac_permission_matrix_v36.md`。
- [x] 已新增只读矩阵导出脚本：`scripts/rbac_permission_matrix.py`。
- [x] 已新增测试：`tests/test_rbac_permission_matrix_v363.py`。
- [x] 默认输出目录：`docs/reports/rbac_permission_matrix/`。
- [x] 权限矩阵覆盖 admin/operator/viewer/auditor 对关键 API 的读写、审批、审计和工具调用边界。
- [x] 输出包含 role hierarchy、allowed roles、denied roles、401/403 拒绝证据、权限申请和定期复核流程。
- [x] 保持现有默认 `rbac_enabled=false` 行为不变。
- [x] 不新增生产登录系统，不绕过 `require_permission`，不改变默认 API token 要求。
- [x] 不宣称权限治理已生产完成，不宣称生产级 SSO/OIDC 或多租户完成。

## 60. v3.6 Phase 16.4 OIDC 生命周期演练计划检查（已完成）

- [x] 已新增 runbook：`docs/oidc_lifecycle_drill_v36.md`。
- [x] 已新增只读演练计划脚本：`scripts/oidc_lifecycle_drill.py`。
- [x] 已新增测试：`tests/test_oidc_lifecycle_drill_v364.py`。
- [x] 默认输出目录：`docs/reports/oidc_lifecycle_drill/`。
- [x] 演练计划覆盖 OIDC 配置预检、token 生命周期、登出与会话失效、JWKS 轮换、client_secret 轮换和失败路径。
- [x] 缺少真实 IdP opt-in 条件时记录为 `skipped`，不得伪造成 success。
- [x] 所有 secret 只输出 env name 与 present 布尔状态。
- [x] 默认不连接真实 IdP，不执行 OIDC token exchange。
- [x] 不修改 `.env`，不默认启用 `AUTH_ENABLED`、`RBAC_ENABLED`、`OIDC_ENABLED`。
- [x] 不宣称生产级 SSO/OIDC 或多租户完成。

## 61. v3.6 Phase 16.5 跨租户审计与拒绝证据检查（已完成）

- [x] 已新增 runbook：`docs/cross_tenant_audit_evidence_v36.md`。
- [x] 已新增只读证据模板脚本：`scripts/cross_tenant_audit_evidence.py`。
- [x] 已新增测试：`tests/test_cross_tenant_audit_evidence_v365.py`。
- [x] 默认输出目录：`docs/reports/cross_tenant_audit_evidence/`。
- [x] 证据模板覆盖 allow、deny、audit record、export redaction、reviewer/owner evidence。
- [x] 已明确未来 audit event 必需 scope 字段：`organization_id`、`tenant_id`、`project_id`、`resource_id`、`actor_principal_id`、`decision`、`denial_reason`。
- [x] 支持引用 RBAC matrix、tenant model 文档和 audit export sample，仅消费元数据。
- [x] 发现 prompt/secret/token/连接串密码原文时输出 `blocked`，且不泄露原文。
- [x] 不修改 audit store schema，不生成伪造的跨租户通过证据，不启用 tenant enforcement，不改 JWT payload。
- [x] 不宣称生产级 SSO/OIDC 或多租户完成。

## 62. v3.6 Phase 16.6 release prep 检查（已完成）

- [x] 版本号已同步到 `3.6.0`（pyproject / FastAPI version / `/health.version` / MCP stdio fallback / script version markers / related tests）。
- [x] 已新增 `RELEASE_NOTES_v3.6.0.md`。
- [x] 已新增 `docs/release_review_v3.6_enterprise_identity_tenant_boundary.md`。
- [x] release notes 覆盖 Phase 16.1~16.5、状态边界与默认 fake/offline 约束。
- [x] release review 覆盖 scope、changed docs/scripts/tests/modules、verification matrix、security/privacy boundary、operational boundary、known limitations、Go/No-Go。
- [x] 前端已移除构建期 Google Fonts 依赖，默认离线 `npm --prefix frontend run build` 可通过。
- [x] 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- [x] 默认 fake/offline 与 pytest/CI 默认不调用真实 LLM 边界保持明确。
- [x] 本轮 release prep 不执行真实外网 LLM，不连接真实外部 IdP。
- [x] 不宣称公网生产可直接上线，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 或多租户完成。

## 63. v3.7 External Integration & Real Provider Acceptance 规划入口检查（当前）

- [x] 已新增规划文档：`docs/v3_7_external_integration_real_provider_acceptance_plan.md`。
- [x] v3.7 定位为 External Integration & Real Provider Acceptance。
- [x] 当前先进入规划与只读基线阶段，版本保持 `3.6.0`。
- [x] 本轮不打 tag、不创建 GitHub Release、不移动历史 tag。
- [x] 明确默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- [x] 明确默认不连接真实外部 MCP，不连接真实业务系统。
- [x] 明确不读取或输出真实 secret 原文。
- [x] Phase 17.1~17.5 与 v3.7.0 release prep 已完成；tag/Release 待用户单独确认。

## 64. v3.7 Phase 17.1 外部集成与真实 provider 基线盘点检查（已完成）

- [x] 已新增 runbook：`docs/external_provider_acceptance_inventory_v37.md`。
- [x] 已新增只读盘点脚本：`scripts/external_provider_acceptance_inventory.py`。
- [x] 已新增测试：`tests/test_external_provider_acceptance_inventory_v371.py`。
- [x] 默认输出目录：`docs/reports/external_provider_acceptance_inventory/`。
- [x] 盘点覆盖 external MCP、real LLM provider、LLM judge、PostgreSQL、Redis、deployment guard、tool approval audit、frontend offline build。
- [x] 输出明确 `read_only=true`、`real_llm_executed=false`、`external_mcp_connected=false`、`business_system_connected=false`。
- [x] 仅输出 env name、present 布尔状态和本地文件存在性，不读取或输出真实 secret 原文。
- [x] 不调用真实外网 LLM，不连接真实外部 MCP，不连接真实业务系统。
- [x] 不宣称真实 provider、真实外部 MCP 或真实业务系统生产验收完成。

## 65. v3.7 Phase 17.2 External MCP acceptance gate 检查（已完成）

- [x] 已新增 runbook：`docs/external_mcp_acceptance_gate_v37.md`。
- [x] 已新增只读门禁脚本：`scripts/external_mcp_acceptance_gate.py`。
- [x] 已新增测试：`tests/test_external_mcp_acceptance_gate_v372.py`。
- [x] 默认输出目录：`docs/reports/external_mcp_acceptance_gate/`。
- [x] 门禁覆盖 real mode opt-in、command configured、command allowlist、tool allowlist、timeout config、lifecycle hardening、approval/audit boundary、fake fixture coverage。
- [x] 输出明确 `external_mcp_connected=false`、`mcp_process_started=false`、`mcp_tools_list_executed=false`、`mcp_tools_call_executed=false`。
- [x] 不启动 MCP subprocess，不执行真实 `tools/list` 或 `tools/call`。
- [x] 不绕过 ToolGateway、PolicyEngine、审批链路或审计链路。
- [x] 不宣称真实外部 MCP 生产验收完成。

## 66. v3.7 Phase 17.3 Real LLM provider acceptance gate 检查（已完成）

- [x] 已新增 runbook：`docs/real_llm_provider_acceptance_gate_v37.md`。
- [x] 已新增只读门禁脚本：`scripts/real_llm_provider_acceptance_gate.py`。
- [x] 已新增测试：`tests/test_real_llm_provider_acceptance_gate_v373.py`。
- [x] 默认输出目录：`docs/reports/real_llm_provider_acceptance_gate/`。
- [x] 门禁覆盖 preflight config、network check gate、smoke opt-in、budget/cache/fallback、PII/prompt guardrails、report redaction、judge acceptance、evidence index。
- [x] 输出明确 `real_llm_executed=false`、`provider_network_check_executed=false`、`pilot_report_content_read=false`。
- [x] 可选索引 pilot report 目录时仅读取文件元数据，不读取报告正文。
- [x] 不调用真实外网 LLM，不执行 provider network check。
- [x] 不读取或输出真实 API key、token、client_secret 或连接串密码原文。
- [x] 不宣称真实 LLM 生产验收完成。
## 68. v3.8 Phase 18.1 SRE observability baseline 检查（当前已完成）

- [x] 已新增 runbook：`docs/sre_observability_baseline_v38.md`。
- [x] 已新增只读脚本：`scripts/sre_observability_baseline.py`。
- [x] 已新增测试：`tests/test_sre_observability_baseline_v381.py`。
- [x] 默认输出目录：`docs/reports/sre_observability_baseline/`，CLI 支持 `--output-dir`。
- [x] 输出包含 JSON + Markdown，并记录 `generated_at`、`commit`、`version`、`phase`、`status`、`checks`、`missing_conditions`、`boundary_declarations` 和输出路径。
- [x] 覆盖 runtime metrics/cost API、runtime snapshot、operations summary、audit export、structured logging、failure diagnostics、backup/restore runbook、外部 APM、告警、容量、备份与 DR 缺口。
- [x] 默认不启动服务，不访问在线 `/health`、`/metrics`、`/operations`、`/runtime/snapshot`。
- [x] 默认不连接真实 APM、日志平台、告警平台或值班系统。
- [x] 默认不执行真实压测、备份恢复或灾备切换，不删除用户数据，不自动清理报告，不修改 `.env`。
- [x] 缺少 SRE/APM/告警/容量/备份/DR opt-in 条件时记录为 `skipped`，不伪造成 `success`。
- [x] 不读取或输出真实 secret、token、API key、client_secret、连接串密码或告警 webhook 原文。
- [x] 不宣称企业级 SRE、RTO/RPO、SLO/SLI、告警触发或生产 DR 验收已完成。
## 69. v3.8 Phase 18.2 SLO/SLI and alerting runbook pack 检查（当前已完成）

- [x] 已新增 runbook：`docs/slo_alerting_runbook_pack_v38.md`。
- [x] 已新增只读脚本：`scripts/slo_alerting_runbook_pack.py`。
- [x] 已新增测试：`tests/test_slo_alerting_runbook_pack_v382.py`。
- [x] 默认输出目录：`docs/reports/slo_alerting_runbook/`，CLI 支持 `--output-dir`。
- [x] 输出包含 JSON + Markdown，并记录 `generated_at`、`commit`、`version`、`phase`、`status`、`checks`、`missing_conditions`、`boundary_declarations` 和输出路径。
- [x] 覆盖 SLO/SLI 指标来源、SLO 目标配置、structured logging 告警上下文、告警分级与路由、on-call 升级、alert dry-run 证据、incident runbook 串联和回归测试覆盖。
- [x] 默认不启动服务，不访问在线 `/health`、`/metrics`、`/operations`、`/runtime/snapshot`。
- [x] 默认不连接真实 APM、日志平台、告警平台或值班系统。
- [x] 默认不发送真实告警，不通知真实 on-call，不调用真实 webhook，不执行真实 incident 升级。
- [x] 缺少 SLO/告警/on-call/dry-run opt-in 或演练证据时记录为 `skipped`，不伪造成 `success`。
- [x] 不读取或输出真实 secret、token、API key、client_secret、连接串密码或告警 webhook 原文。
- [x] 不宣称企业级 SLO/SLI、告警触发、on-call 响应或 incident 升级生产验收已完成。
## 70. v3.8 Phase 18.3 Backup/restore and DR drill evidence pack 检查（当前已完成）

- [x] 已新增 runbook：`docs/backup_restore_dr_evidence_pack_v38.md`。
- [x] 已新增只读脚本：`scripts/backup_restore_dr_evidence_pack.py`。
- [x] 已新增测试：`tests/test_backup_restore_dr_evidence_pack_v383.py`。
- [x] 默认输出目录：`docs/reports/backup_restore_dr_evidence/`，CLI 支持 `--output-dir`。
- [x] 输出包含 JSON + Markdown，并记录 `generated_at`、`commit`、`version`、`phase`、`status`、`checks`、`missing_conditions`、`boundary_declarations` 和输出路径。
- [x] 覆盖备份范围、部署与迁移边界、RTO/RPO 配置、备份演练证据、恢复 dry-run 证据、DR failover 证据、runbook 串联和回归测试覆盖。
- [x] 默认不启动服务，不连接真实 PostgreSQL、Redis、对象存储、IdP、LLM provider 或外部 MCP。
- [x] 默认不执行真实备份，不执行真实恢复，不执行灾备切换，不执行 Alembic migration。
- [x] 默认不写业务数据、审计数据或指标数据，不删除用户数据，不移动或清理报告，不修改 `.env`。
- [x] 缺少备份/恢复/DR opt-in 或演练证据时记录为 `skipped`，不伪造成 `success`。
- [x] 不读取或输出真实 secret、token、API key、client_secret、`DATABASE_URL`、`REDIS_URL` 或对象存储凭证原文。
- [x] 不宣称 RTO/RPO、真实恢复、DR failover 或生产 DR 验收已完成。
## 71. v3.8 Phase 18.4 Capacity and load-test readiness plan 检查（当前已完成）

- [x] 已新增 runbook：`docs/capacity_load_test_readiness_plan_v38.md`。
- [x] 已新增只读脚本：`scripts/capacity_load_test_readiness_plan.py`。
- [x] 已新增测试：`tests/test_capacity_load_test_readiness_plan_v384.py`。
- [x] 默认输出目录：`docs/reports/capacity_load_test_readiness/`，CLI 支持 `--output-dir`。
- [x] 输出包含 JSON + Markdown，并记录 `generated_at`、`commit`、`version`、`phase`、`status`、`checks`、`missing_conditions`、`boundary_declarations` 和输出路径。
- [x] 覆盖关键 API 入口、流量模型目标、request guard、容量测试可观测性、load-test dry-run 证据、soak test 证据、runbook 串联和回归测试覆盖。
- [x] 默认不启动服务，不访问在线端点，不执行真实压测、soak test、并发请求或容量探测。
- [x] 默认不连接真实 PostgreSQL、Redis、APM、日志平台、告警平台、IdP、LLM provider、外部 MCP 或业务系统。
- [x] 默认不写业务数据、审计数据或指标数据，不删除用户数据，不清理报告，不修改 `.env`。
- [x] 缺少容量/压测/soak opt-in 或报告证据时记录为 `skipped`，不伪造成 `success`。
- [x] 不读取或输出真实 secret、token、API key、client_secret、连接串密码或压测目标 URL 原文。
- [x] 不宣称真实压测、长期稳定性或生产容量上限验收已完成。
## 72. v3.8.0 release prep 检查（当前已完成）

- [x] 版本号已同步到 `3.8.0`（pyproject / FastAPI version / `/health.version` / MCP stdio fallback / v3.8 script version markers / related tests）。
- [x] 已新增 `RELEASE_NOTES_v3.8.0.md`。
- [x] 已新增 `docs/release_review_v3.8_sre_observability_dr.md`。
- [x] release notes 覆盖 Phase 18.1~18.4、状态语义与默认 fake/offline 约束。
- [x] release review 覆盖 scope、changed files、verification matrix、security/privacy boundary、operational boundary、known limitations、Go/No-Go。
- [x] 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- [x] 默认 fake/offline 与 pytest/CI 默认不调用真实 LLM 边界保持明确。
- [x] 本轮不连接真实 APM、日志、告警、对象存储、PostgreSQL、Redis、IdP、外部 MCP 或业务系统。
- [x] 本轮不执行真实告警、on-call 通知、压测、备份恢复、DR failover 或 Alembic migration。
- [x] 全量回归 `python -m pytest -q` 通过：900 passed, 4 skipped, 2 warnings。
- [x] `git diff --check` 通过，仅 CRLF 提示。
- [x] 不宣称公网生产可直接上线，不宣称企业级 SRE、RTO/RPO、DR、容量上限、真实 LLM 生产验收、生产级 SSO/OIDC 或多租户完成。
## 73. v3.9 Compliance Security Hardening 规划入口检查（当前）

- [x] 已新增规划文档：`docs/v3_9_compliance_security_hardening_plan.md`。
- [x] v3.9 定位为 Compliance Security Hardening。
- [x] 当前已进入 v3.9.0 release prep，版本已同步到 `3.9.0`。
- [x] 本轮不打 tag，不创建 GitHub Release，不移动历史 tag。
- [x] 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- [x] 默认不连接真实 IdP、APM、日志平台、告警平台、对象存储、PostgreSQL、Redis、外部 MCP 或业务系统。
- [x] 默认不执行真实安全扫描、真实密钥轮换、真实权限变更、真实审计导出、真实发布或真实回滚。
- [x] 不读取或输出真实 secret 原文，不宣称企业级合规、安全治理、发布门禁或密钥治理完成。

## 74. v3.9 Phase 19.1 Compliance security baseline inventory 检查（当前已完成）

- [x] 已新增 runbook：`docs/compliance_security_baseline_v39.md`。
- [x] 已新增只读脚本：`scripts/compliance_security_baseline.py`。
- [x] 已新增测试：`tests/test_compliance_security_baseline_v391.py`。
- [x] 默认输出目录：`docs/reports/compliance_security_baseline/`，CLI 支持 `--output-dir`。
- [x] 输出包含 JSON + Markdown，并记录 `generated_at`、`commit`、`version`、`phase`、`status`、`checks`、`missing_conditions`、`boundary_declarations` 和输出路径。
- [x] 覆盖 deployment guard、安全响应头、request guard、结构化日志脱敏、审计留存与导出、RBAC、OIDC、prompt injection、PII guard、跨租户审计和 release review 证据缺口。
- [x] 默认不启动服务，不访问在线端点，不连接真实外部系统。
- [x] 默认不执行真实安全扫描、审计导出、密钥轮换、权限变更、发布或回滚。
- [x] 缺少正式合规签核、审计复核、发布门禁复核或密钥轮换演练证据时记录为 `skipped`，不伪造成 `success`。
- [x] 不读取或输出真实 secret、token、API key、client_secret、连接串密码、告警 webhook 或生产 URL 原文。
- [x] 不宣称企业级合规、安全治理、发布门禁或密钥治理验收完成。
## 75. v3.9 Phase 19.2 Secret rotation and leakage response pack 检查（当前已完成）

- [x] 已新增 runbook：`docs/secret_rotation_leakage_response_pack_v39.md`。
- [x] 已新增只读脚本：`scripts/secret_rotation_leakage_response_pack.py`。
- [x] 已新增测试：`tests/test_secret_rotation_leakage_response_pack_v392.py`。
- [x] 默认输出目录：`docs/reports/secret_rotation_leakage_response/`，CLI 支持 `--output-dir`。
- [x] 输出包含 JSON + Markdown，并记录 `generated_at`、`commit`、`version`、`phase`、`status`、`checks`、`missing_conditions`、`boundary_declarations` 和输出路径。
- [x] 覆盖 JWT/OIDC/数据库/Redis/LLM/MCP/业务系统/告警 webhook 等 secret surface、脱敏审计边界、身份密钥生命周期、外部集成密钥边界、治理例外串联、轮换/泄漏响应/撤销恢复演练证据缺口。
- [x] 默认不读取 `.env` 或真实 secret 值。
- [x] 默认不连接真实 KMS、Vault、云平台、IdP、LLM provider、外部 MCP、数据库、Redis、告警平台或业务系统。
- [x] 默认不执行真实密钥创建、轮换、撤销、禁用、泄漏扫描或告警通知。
- [x] 默认不修改用户、角色、权限、租户、业务数据、审计数据、指标数据或配置文件。
- [x] 缺少轮换、泄漏响应或撤销恢复演练证据时记录为 `skipped`，不伪造成 `success`。
- [x] 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- [x] 不宣称企业级密钥治理完成。
## 76. v3.9 Phase 19.3 Release gate and rollback governance pack 检查（当前已完成）

- [x] 已新增 runbook：`docs/release_gate_rollback_governance_pack_v39.md`。
- [x] 已新增只读脚本：`scripts/release_gate_rollback_governance_pack.py`。
- [x] 已新增测试：`tests/test_release_gate_rollback_governance_pack_v393.py`。
- [x] 默认输出目录：`docs/reports/release_gate_rollback_governance/`，CLI 支持 `--output-dir`。
- [x] 输出包含 JSON + Markdown，并记录 `generated_at`、`commit`、`version`、`phase`、`status`、`checks`、`missing_conditions`、`boundary_declarations` 和输出路径。
- [x] 覆盖 deployment guard、compose、Alembic、release notes、release review、变更审批、发布签核、回滚演练、治理例外和安全合规串联证据缺口。
- [x] 默认不启动服务，不访问在线端点。
- [x] 默认不执行 git tag、GitHub Release、部署、迁移、回滚、数据恢复或外部系统调用。
- [x] 默认不连接真实 PostgreSQL、Redis、IdP、LLM provider、外部 MCP、业务系统、APM、日志平台或告警平台。
- [x] 缺少变更审批、发布签核或回滚演练证据时记录为 `skipped`，不伪造成 `success`。
- [x] 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- [x] 不宣称生产发布门禁或回滚验收完成。
## 77. v3.9 Phase 19.4 Security regression and compliance evidence pack 检查（当前已完成）

- [x] 已新增 runbook：`docs/security_regression_compliance_evidence_pack_v39.md`。
- [x] 已新增只读脚本：`scripts/security_regression_compliance_evidence_pack.py`。
- [x] 已新增测试：`tests/test_security_regression_compliance_evidence_pack_v394.py`。
- [x] 默认输出目录：`docs/reports/security_regression_compliance_evidence/`，CLI 支持 `--output-dir`。
- [x] 输出包含 JSON + Markdown，并记录 `generated_at`、`commit`、`version`、`phase`、`status`、`checks`、`missing_conditions`、`boundary_declarations` 和输出路径。
- [x] 覆盖 prompt injection、PII 泄漏、SQL guard、边界防护、身份/RBAC、跨租户拒绝、审计导出脱敏、发布门禁和合规证据串联缺口。
- [x] 默认不启动服务，不访问在线端点。
- [x] 默认不执行真实 SAST、DAST、依赖扫描、红队测试、外部审计或外部系统调用。
- [x] 默认不连接真实 IdP、LLM provider、外部 MCP、业务系统、数据库、Redis、APM、日志平台或告警平台。
- [x] 缺少外部安全扫描、正式安全签核或合规证据复核时记录为 `skipped`，不伪造成 `success`。
- [x] 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- [x] 不宣称企业级安全合规验收完成。
## 78. v3.9.0 release prep 检查（当前已完成）

- [x] 版本号已同步到 `3.9.0`（pyproject / FastAPI version / `/health.version` / MCP stdio fallback / v3.9 script version markers / related tests）。
- [x] 已新增 `RELEASE_NOTES_v3.9.0.md`。
- [x] 已新增 `docs/release_review_v3.9_compliance_security_hardening.md`。
- [x] release notes 覆盖 Phase 19.1~19.4、状态语义与默认 fake/offline 约束。
- [x] release review 覆盖 scope、changed files、verification matrix、security/privacy boundary、operational boundary、known limitations、Go/No-Go。
- [x] v3.9 聚焦验证 `python -m pytest tests/test_runtime_hardening_v055.py tests/test_operations_summary_v312.py tests/test_mcp_stdio_client_v31.py tests/test_compliance_security_baseline_v391.py tests/test_secret_rotation_leakage_response_pack_v392.py tests/test_release_gate_rollback_governance_pack_v393.py tests/test_security_regression_compliance_evidence_pack_v394.py -q` 通过：56 passed, 2 warnings。
- [x] v3.9 安全/合规回归 `python -m pytest tests/test_compliance_security_baseline_v391.py tests/test_secret_rotation_leakage_response_pack_v392.py tests/test_release_gate_rollback_governance_pack_v393.py tests/test_security_regression_compliance_evidence_pack_v394.py tests/test_security_v04.py tests/test_guardrails_v44.py tests/test_guardrails_pii_leak_v44.py tests/test_security_headers_v71.py tests/test_request_guards_v72.py tests/test_auth_v20.py tests/test_rbac_v20.py tests/test_cross_tenant_audit_evidence_v365.py tests/test_audit_v045.py tests/test_audit_retention_export_v74.py tests/test_deployment_guard_v60.py -q` 通过：161 passed, 2 warnings。
- [x] 全量回归 `python -m pytest -q` 通过：920 passed, 4 skipped, 2 warnings。
- [x] `git diff --check` 通过，仅 CRLF 提示。
- [x] 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- [x] 默认 fake/offline 与 pytest/CI 默认不调用真实 LLM 边界保持明确。
- [x] 本轮不连接真实外部系统，不执行真实安全扫描、红队测试、审计导出、密钥轮换、权限变更、发布、回滚或迁移。
- [x] 不宣称公网生产可直接上线，不宣称企业级合规、安全治理、密钥治理、发布门禁、回滚验收、真实 LLM 生产验收、生产级 SSO/OIDC 或多租户完成。

## 79. v4.0 Production Launch Readiness Review 规划入口检查（当前已完成）

- [x] 已新增规划文档：`docs/v4_0_production_launch_readiness_plan.md`。
- [x] v4.0 定位为 Production Launch Readiness Review。
- [x] 当前进入只读证据汇总阶段，不同步版本号，不打 tag，不创建 GitHub Release。
- [x] 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- [x] 默认不连接真实 IdP、LLM provider、外部 MCP、业务系统、PostgreSQL、Redis、APM、日志、告警、KMS、Vault、对象存储或云平台。
- [x] 默认不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、红队测试、审计导出、密钥轮换或权限变更。
- [x] 不读取或输出真实 secret 原文，不把 `skipped/blocked/partial` 或只读本地证据汇总伪造成生产 Go。

## 80. v4.0 Phase 20.1 Launch readiness evidence review pack 检查（当前已完成）

- [x] 已新增 runbook：`docs/production_launch_readiness_review_v40.md`。
- [x] 已新增只读脚本：`scripts/production_launch_readiness_review.py`。
- [x] 已新增测试：`tests/test_production_launch_readiness_review_v401.py`。
- [x] 默认输出目录：`docs/reports/production_launch_readiness/`，CLI 支持 `--output-dir`。
- [x] 输出包含 JSON + Markdown，并记录 `generated_at`、`commit`、`version`、`phase`、`status`、`input_sources`、`local_artifacts`、`production_blockers`、`missing_conditions`、`go_no_go`、`boundary_declarations` 和输出路径。
- [x] 覆盖 v3.5~v3.9 试点收口、证据归档、真实 provider 验收、SRE/DR、容量、安全合规、发布门禁和回滚治理证据入口。
- [x] 默认状态为 `partial`，Go/No-Go 建议为 `Manual-Review`，公网生产直上为 `No-Go`。
- [x] 缺少真实 SSO/OIDC、租户隔离、真实 LLM、外部 MCP、业务系统集成、SRE/DR、容量、安全合规、发布门禁或回滚演练证据时保留阻断项，不伪造成 `success`。
- [x] 检测到 secret-like 输入、非只读输入、意外真实 LLM/MCP 执行、意外 tag/release 标记时输出 `blocked`。
- [x] 上游来源状态为 `blocked/failed` 时整体保持 `blocked`，不降级为 `partial`。
- [x] 提供了输入但路径不存在、无法加载或全部来源为 `skipped` 时整体可保持 `skipped` 语义。
- [x] secret-like 检测覆盖常见 JSON 键值形态（如 `token`、`client_secret`、`password`、连接串），输出前保持脱敏。
- [x] `controlled_internal_pilot` 在整体 `blocked` 时收紧为 `No-Go`，避免和阻断状态冲突。
- [x] 根据子 agent 审查补强 `external_system_connected` 边界违规识别。
- [x] v4.0 + v3.9 关联验证 `python -m pytest tests/test_production_launch_readiness_review_v401.py tests/test_compliance_security_baseline_v391.py tests/test_secret_rotation_leakage_response_pack_v392.py tests/test_release_gate_rollback_governance_pack_v393.py tests/test_security_regression_compliance_evidence_pack_v394.py -q` 通过：27 passed, 1 warning。
- [x] 默认不启动服务，不访问在线端点，不连接真实外部系统，不执行真实生产操作。
- [x] 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- [x] 不自动改变最终生产 Go/No-Go 结论，不宣称生产上线批准完成。

## 81. v4.0 Phase 20.2 Launch blocker register 检查（当前已完成）

- [x] 已新增 runbook：`docs/launch_blocker_register_v40.md`。
- [x] 已新增只读脚本：`scripts/launch_blocker_register.py`。
- [x] 已新增测试：`tests/test_launch_blocker_register_v402.py`。
- [x] 默认输出目录：`docs/reports/launch_blockers/`，CLI 支持 `--output-dir`。
- [x] 支持 `--launch-readiness` 读取 Phase 20.1 JSON 结构化字段，生成 blocker register。
- [x] 输出包含 JSON + Markdown，并记录 `generated_at`、`commit`、`version`、`phase`、`status`、`launch_readiness_source`、`blocker_register`、`missing_conditions`、`go_no_go`、`boundary_declarations` 和输出路径。
- [x] 每个 blocker 包含 blocker id、来源、风险描述、影响范围、责任人、到期时间、补偿控制、关闭证据、状态、审批状态和下一步动作。
- [x] 默认无上游输入或上游 `skipped` 时输出 `skipped`，不伪造成 `open/success`。
- [x] 存在待关闭 blocker 时输出 `partial`；上游 `blocked/failed`、secret-like 输入、自动批准/关闭标记或边界违规时输出 `blocked`。
- [x] `auto_approved=false`、`auto_closed=false`，不自动批准上线，不自动关闭阻断项。
- [x] 根据子 agent 审查补强上游 `skipped` 保留、`auto_approved/auto_closed` 阻断和 success 语义文档。
- [x] v4.0 Phase 20.1/20.2 + v3.9 关键安全合规关联验证 `python -m pytest tests/test_production_launch_readiness_review_v401.py tests/test_launch_blocker_register_v402.py tests/test_compliance_security_baseline_v391.py tests/test_secret_rotation_leakage_response_pack_v392.py tests/test_release_gate_rollback_governance_pack_v393.py tests/test_security_regression_compliance_evidence_pack_v394.py -q` 通过：34 passed, 1 warning。
- [x] `git diff --check` 通过，仅 CRLF 提示。
- [x] 默认不启动服务，不访问在线端点，不连接真实外部系统，不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、审计导出、密钥轮换或权限变更。
- [x] 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- [x] 不改版本号，不打 tag，不创建 GitHub Release，不宣称生产上线批准完成。

## 82. v4.0 Phase 20.3 Production runbook finalization 检查（当前已完成）

- [x] 已新增 runbook：`docs/production_runbook_finalization_v40.md`。
- [x] 已新增只读脚本：`scripts/production_runbook_finalization.py`。
- [x] 已新增测试：`tests/test_production_runbook_finalization_v403.py`。
- [x] 默认输出目录：`docs/reports/production_runbook_finalization/`，CLI 支持 `--output-dir`。
- [x] 支持 `--launch-readiness` 与 `--launch-blockers` 串联 Phase 20.1/20.2 JSON 结构化字段。
- [x] 输出包含 JSON + Markdown，并记录 `generated_at`、`commit`、`version`、`phase`、`status`、`input_sources`、`runbook_items`、`missing_conditions`、`go_no_go`、`boundary_declarations` 和输出路径。
- [x] 覆盖部署、回滚、incident、DR、密钥轮换、审计导出、SLO/告警、容量、Launch Readiness 和 blocker register 的本地 runbook 入口。
- [x] 默认仅检查本地文件存在性和可选上游 JSON 结构化字段，不读取 Markdown 报告正文。
- [x] 输出明确 `deployment_executed=false`、`rollback_executed=false`、`alert_sent=false`、`oncall_notified=false`、`auto_approved=false`、`auto_closed=false`。
- [x] 缺少上游 Phase 20.1/20.2 JSON 时输出 `skipped`，不降级为 `partial`。
- [x] 透传 Phase 20.2 blocker 计数与上游 Go/No-Go，保留 open/blocked/skipped blocker 汇总证据。
- [x] audit log/export 文档与 `tests/test_audit_retention_export_v74.py` 纳入必需入口，不静默降级为非必需。
- [x] Phase 20.1 在 `skipped` 时 `controlled_internal_pilot=Needs-Input`，不显示 `Review-Allowed`。
- [x] v4.0 Phase 20.1/20.2/20.3 + v3.9 关键安全合规关联验证 `python -m pytest tests/test_production_launch_readiness_review_v401.py tests/test_launch_blocker_register_v402.py tests/test_production_runbook_finalization_v403.py tests/test_compliance_security_baseline_v391.py tests/test_secret_rotation_leakage_response_pack_v392.py tests/test_release_gate_rollback_governance_pack_v393.py tests/test_security_regression_compliance_evidence_pack_v394.py -q` 通过：39 passed。
- [x] `git diff --check` 通过，仅 CRLF 提示。
- [x] 默认不启动服务，不访问在线端点，不连接真实外部系统，不执行真实生产操作。
- [x] 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- [x] 不把 runbook 入口存在性伪造成生产 Go，不改版本号，不打 tag，不创建 GitHub Release。

## 90. v4.3.0 release prep 检查（当前已完成）

- [x] 版本号已同步到 `4.3.0`（pyproject / FastAPI version / `/health.version` / MCP stdio fallback / related tests）。
- [x] 已新增 `RELEASE_NOTES_v4.3.0.md`。
- [x] 已新增 `docs/release_review_v4.3_operational_governance_console_readiness.md`。
- [x] release notes 覆盖 v4.0~v4.3 的生产上线评审、上线阻断项、关闭证据、人工签核、受控生产验收、验收缺口和运营治理台只读展示。
- [x] release review 覆盖 scope、changed files、verification matrix、security/privacy boundary、operational boundary 和 Go/No-Go。
- [x] 默认 fake/offline 与 pytest/CI 默认不调用真实 LLM 边界保持明确。
- [x] 本轮不连接真实外部系统，不执行真实发布、迁移、回滚、压测、备份恢复、DR failover、安全扫描、审计导出、密钥轮换或权限变更。
- [x] 本轮 release prep 不打 `v4.3.0` tag，不创建 GitHub Release，不移动历史 tag。
- [x] 不宣称公网生产可直接上线，不宣称真实 LLM/MCP/IdP/PostgreSQL/Redis/业务系统生产验收完成，不宣称生产级 SSO/OIDC、多租户、复杂 BI、企业级 SRE/DR/容量验收完成。

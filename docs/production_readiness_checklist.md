# 生产就绪检查清单（v3.4.0 release prep / Pilot Hardening & Operator Experience）

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

- [ ] 当前后端全量基线为 807 passed, 4 skipped（若再次全量验证变化，以最新结果为准）
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

## 34. v3.2.0 release prep 收口检查（当前）

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
- [ ] v3.5 定位为 Controlled Pilot Expansion & Evidence Operations。
- [ ] 规划覆盖 Phase 15.1~15.6：
  - Phase 15.1 Pilot evidence comparison snapshot。
  - Phase 15.2 Operator drill scoring rubric。
  - Phase 15.3 Controlled integration dry-run checklist。
  - Phase 15.4 Governance exception register。
  - Phase 15.5 Pilot closeout report pack。
  - Phase 15.6 v3.5 release prep。
- [ ] 当前版本保持 `3.4.0`，直到 v3.5 release prep 阶段再同步版本号。
- [ ] `v3.4.0` GitHub Release 已完成，历史 tags 保持不变。
- [ ] 规划轮次保持边界：默认 fake/offline，默认 pytest/CI 不调用真实 LLM，默认不执行真实外网 LLM。
- [ ] 本轮不改业务逻辑、不改版本号、不打 tag、不创建 Release。
- [ ] 不读取或输出真实 secret 原文。
- [ ] 不宣称公网生产直上，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC 或多租户/复杂 BI 全量完成。

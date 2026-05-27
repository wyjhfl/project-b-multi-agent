# RELEASE_NOTES_v3.0.0

## 版本定位

v3.0.0 交付 **Final Production Landing（企业内网试点 / 准生产演示）** 收口能力，目标是完成 v3 最终阶段的演练、复核与发布前材料归档。

## Phase 10.1 ~ 10.4 交付摘要

### Phase 10.1：真实 LLM opt-in 执行记录模板

- 新增执行记录模板文档：`docs/real_llm_pilot_execution_log_v30.md`。
- 仅在显式 opt-in 且环境齐全时执行真实 LLM smoke。
- 本轮记录为 skipped（未执行真实外网 LLM）。

### Phase 10.2：生产部署演练与回滚

- 新增演练文档：`docs/production_deployment_drill_v30.md`。
- 覆盖 compose/prod_config_check 校验、失败场景、回滚步骤、执行模板。
- 保持“本地/内网试点模拟”边界，不等于公网生产上线。

### Phase 10.3：运维监控与备份恢复 runbook

- 新增文档：`docs/operations_monitoring_backup_drill_v30.md`。
- 覆盖 `/health`、`/deployment/check`、`/metrics/runtime`、`/llm/pilot/reports`、`/audit/events/export` 检查项。
- 补齐 SQLite / PostgreSQL / Redis 备份恢复模板与留存清理边界。

### Phase 10.4：安全复核与 Go/No-Go

- 新增文档：`docs/security_go_no_go_review_v30.md`。
- 复核 deployment guard、HTTP 安全基线、结构化日志脱敏、审计导出、LLM 受控试点边界、OIDC 预检边界。
- 结论收口：
  - Go：企业内网试点 / 准生产演示
  - No-Go：公网生产直接上线

## 默认路径与边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 真实 LLM smoke 仍为 opt-in。
- 不接真实外部 MCP 作为默认依赖。
- 本轮未执行真实外网 LLM。

## 验证摘要（release prep）

- 后端全量：`750 passed, 4 skipped`
- 前端：`npm run lint` / `npm run build` 通过
- `docker compose config` 通过
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`：
  - 缺变量按预期失败
  - 注入临时 `JWT_SECRET` / `DATABASE_URL` / `REDIS_URL` 后通过

## 与 v2.9.0 的关系

- v2.9.0 tag 与 GitHub Release 已发布完成。
- main 超前 v2.9.0 tag 属于 v3.0.0 release prep 后续演进。
- 本次仅做 v3.0.0 release prep，不改动 v2.9.0 tag。

## 声明

- v3.0.0 不等于公网生产可直接上线。
- v3.0.0 不等于完整生产级 SSO/OIDC、多租户、复杂 BI 完成。
- v3.0.0 不等于真实 LLM 生产验收完成。

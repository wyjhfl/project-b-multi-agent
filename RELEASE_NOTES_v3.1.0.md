# RELEASE_NOTES_v3.1.0

## 版本定位

v3.1.0 交付 **Productization Enhancement**，面向企业内网试点后的产品可用性、观测性、演示闭环与运维体验增强。

> 边界：v3.1.0 不等于公网生产直接上线，不等于真实 LLM 生产验收完成，不等于生产级 SSO/OIDC、多租户、复杂 BI 全量完成。

## Phase 11.1 ~ 11.5 交付摘要

### Phase 11.1：离线 demo seed + demo_e2e 脚本

- 新增离线演示数据与端到端脚本：
  - `scripts/demo_seed_data.py`
  - `scripts/demo_e2e.ps1`
  - `docs/demo_e2e_runbook_v31.md`
- 默认 fake/offline，不依赖真实外部 MCP，不调用真实外网 LLM。

### Phase 11.2：只读运营总览

- 新增后端只读聚合接口：`GET /operations/summary`。
- 新增前端只读入口：`/operations`。
- 汇总 health / deployment / metrics / audit / tasks / approvals / pilot reports / demo evidence。
- 仅只读展示，不提供密钥录入，不提供真实 LLM 执行按钮，不提供写操作/删除操作。

### Phase 11.3：真实 LLM opt-in 执行记录

- 新增执行记录：`docs/real_llm_pilot_execution_log_v31.md`。
- 本轮因 opt-in 环境变量缺失，记录为 `skipped`。
- 本轮未执行真实外网 LLM，未伪造成功报告。

### Phase 11.4：OIDC/SSO 最小真实 IdP 配置演练文档

- 新增文档：`docs/oidc_minimal_idp_drill_v31.md`。
- 覆盖最小配置、development/production 差异、状态检查、常见失败与回滚。
- 明确当前仅为最小演练与预检，不宣称生产级 SSO/OIDC 完成。

### Phase 11.5：运维排障与备份恢复 polish

- 新增运维排障索引：`docs/operations_troubleshooting_index_v31.md`。
- 新增备份恢复检查清单：`docs/backup_restore_checklist_v31.md`。
- 统一“不删除用户数据”恢复原则，保留脱敏与导出边界。

## 默认路径与安全边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 真实 LLM 仅 opt-in。
- 不提交 API key/token/client_secret/JWT_SECRET/DATABASE_URL/REDIS_URL 等真实凭据。
- 不默认接入真实外部 MCP。

## 验证基线（release prep）

- 本轮全量基线：`754 passed, 4 skipped`（若后续复跑变化，以最新实测为准）。
- `docker compose config` 通过。
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` 缺变量按预期失败，注入临时变量后通过。
- 前端 `npm run lint` / `npm run build` 通过。

## 与 v3.0.0 的关系

- v3.0.0 tag 与 GitHub Release 已完成且保持不变。
- 当前 main 超前 v3.0.0 tag 属于 v3.1.0 release prep 演进。
- 本轮仅做 v3.1.0 release prep，不打 tag，不创建 GitHub Release。

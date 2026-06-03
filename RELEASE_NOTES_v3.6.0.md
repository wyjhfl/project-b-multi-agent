# v3.6.0 发布说明

## 摘要

v3.6.0 = **Enterprise Identity & Tenant Boundary**。

本轮 release prep 汇总 Phase 16.1~16.5 的企业身份、权限矩阵、OIDC 生命周期、租户归属模型和跨租户审计拒绝证据模板。当前仍是受控试点与准生产验收准备，不等于生产级 SSO/OIDC 或多租户全量完成。

## 阶段覆盖

### Phase 16.1 - 身份与租户边界盘点

- 新增 `docs/identity_tenant_boundary_inventory_v36.md`。
- 新增 `scripts/identity_tenant_boundary_inventory.py` 与 `tests/test_identity_tenant_boundary_inventory_v361.py`。
- 盘点 `User`、`TokenPayload`、`UserRole`、JWT、RBAC、OIDC 配置预检、审计边界和资源归属缺口。
- 当前缺失 tenant/org/project/resource ownership 时记录为 `gap`，不伪造成完成。

### Phase 16.2 - 租户归属模型草案

- 新增 `docs/tenant_ownership_model_v36.md`。
- 新增 `TenantOwnershipModelDraft` 及相关 Pydantic 草案模型。
- 新增 `tests/test_tenant_ownership_model_v362.py`。
- 明确 `organization`、`tenant`、`project`、`principal`、`role_assignment`、`resource_scope`、`audit_scope` 概念边界。
- 当前不迁移数据库、不改 user store、不改 JWT payload、不启用 tenant enforcement。

### Phase 16.3 - RBAC 权限矩阵强化

- 新增 `docs/rbac_permission_matrix_v36.md`。
- 新增 `scripts/rbac_permission_matrix.py` 与 `tests/test_rbac_permission_matrix_v363.py`。
- 导出 admin/operator/viewer/auditor 对 tasks、approvals、audit、metrics、tools、eval、memory、reflection、snapshot 的权限矩阵。
- 保留 401/403 拒绝证据、权限申请、定期复核和最小权限口径。

### Phase 16.4 - OIDC 生命周期演练计划

- 新增 `docs/oidc_lifecycle_drill_v36.md`。
- 新增 `scripts/oidc_lifecycle_drill.py` 与 `tests/test_oidc_lifecycle_drill_v364.py`。
- 覆盖 OIDC 配置预检、token 生命周期、登出、JWKS 轮换、client_secret 轮换和失败路径。
- 缺少真实 IdP opt-in 条件时记录为 `skipped`；默认不连接真实 IdP，不执行 token exchange。

### Phase 16.5 - 跨租户审计与拒绝证据

- 新增 `docs/cross_tenant_audit_evidence_v36.md`。
- 新增 `scripts/cross_tenant_audit_evidence.py` 与 `tests/test_cross_tenant_audit_evidence_v365.py`。
- 证据模板覆盖 allow、deny、audit record、export redaction、reviewer/owner evidence。
- 明确未来 audit event 必需 scope 字段：`organization_id`、`tenant_id`、`project_id`、`resource_id`、`actor_principal_id`、`decision`、`denial_reason`。
- 发现 prompt/secret/token/连接串密码原文时输出 `blocked`，且不泄露原文。

## 版本同步

- `pyproject.toml` 已同步到 `3.6.0`。
- FastAPI `app.version` 与 `/health.version` 已同步到 `3.6.0`。
- MCP stdio fallback client version 已同步到 `3.6.0`。
- 脚本 version markers 与相关测试断言已同步到 `3.6.0`。
- 前端移除构建期 Google Fonts 依赖，改用系统字体栈，保持离线构建可通过。

## 边界声明

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 默认不连接真实外部 IdP，不执行 OIDC token exchange。
- 默认不启用 `AUTH_ENABLED`、`RBAC_ENABLED`、`OIDC_ENABLED`。
- 不提交或输出真实密钥、Token、API Key、client_secret、JWT_SECRET、DATABASE_URL、REDIS_URL。
- 不修改 audit store schema。
- 不改 JWT payload。
- 不启用 tenant enforcement。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户或复杂 BI 全量完成。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。

## 验证

- `python -m pytest tests/test_identity_tenant_boundary_inventory_v361.py tests/test_tenant_ownership_model_v362.py tests/test_rbac_permission_matrix_v363.py tests/test_oidc_lifecycle_drill_v364.py tests/test_cross_tenant_audit_evidence_v365.py -q`
- `python -m pytest tests/test_runtime_hardening_v055.py tests/test_mcp_stdio_client_v31.py tests/test_operations_summary_v312.py tests/test_acceptance_snapshot_v321.py -q`
- `python -m pytest tests/test_auth_v20.py tests/test_rbac_v20.py tests/test_oidc_config_v75.py tests/test_audit_v045.py tests/test_audit_retention_export_v74.py -q`
- `python -m pytest -q`：855 passed, 4 skipped, 2 warnings。
- `docker compose config`
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`
- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `git diff --check`

最终 tag 与 GitHub Release 创建需用户单独确认。

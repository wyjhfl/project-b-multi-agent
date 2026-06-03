# v3.6.0 发布复核 - Enterprise Identity & Tenant Boundary

## 范围

- 完成 v3.6 Phase 16.1~16.5 交付收口。
- 同步版本标记到 `3.6.0`。
- 新增 release notes、release review、验证矩阵与 tag 决策前边界声明。
- 本轮不打 tag，不创建 GitHub Release。

## 变更文档 / 脚本 / 测试 / 模块

- 版本同步：`pyproject.toml`、`app/main.py`、`app/tools/mcp/stdio_client.py`。
- 前端离线构建修复：`frontend/src/app/layout.tsx`、`frontend/src/app/globals.css` 移除构建期 Google Fonts 依赖，改用系统字体栈。
- 脚本版本字段：acceptance snapshot、v3.4/v3.5 evidence scripts、v3.6 identity/tenant/RBAC/OIDC/audit evidence scripts。
- 新增文档：
  - `docs/identity_tenant_boundary_inventory_v36.md`
  - `docs/tenant_ownership_model_v36.md`
  - `docs/rbac_permission_matrix_v36.md`
  - `docs/oidc_lifecycle_drill_v36.md`
  - `docs/cross_tenant_audit_evidence_v36.md`
  - `RELEASE_NOTES_v3.6.0.md`
- 新增脚本：
  - `scripts/identity_tenant_boundary_inventory.py`
  - `scripts/rbac_permission_matrix.py`
  - `scripts/oidc_lifecycle_drill.py`
  - `scripts/cross_tenant_audit_evidence.py`
- 新增测试：
  - `tests/test_identity_tenant_boundary_inventory_v361.py`
  - `tests/test_tenant_ownership_model_v362.py`
  - `tests/test_rbac_permission_matrix_v363.py`
  - `tests/test_oidc_lifecycle_drill_v364.py`
  - `tests/test_cross_tenant_audit_evidence_v365.py`
- 新增模型草案：
  - `OrganizationScopeDraft`
  - `TenantScopeDraft`
  - `ProjectScopeDraft`
  - `PrincipalScopeDraft`
  - `RoleAssignmentDraft`
  - `ResourceScopeDraft`
  - `AuditScopeDraft`
  - `TenantOwnershipModelDraft`

## 验证矩阵

| 验证项 | 结果口径 |
|--------|----------|
| Phase 16.1~16.5 目标测试 | 24 passed, 1 warning |
| runtime / health / MCP stdio / operations / acceptance version 回归 | 41 passed, 2 warnings |
| auth / RBAC / OIDC / audit 相关回归 | 72 passed, 2 warnings |
| `python -m pytest -q` | 855 passed, 4 skipped, 2 warnings |
| `docker compose config` | 通过；Docker 用户配置读权限 warning 不影响 compose 解析 |
| `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` | 使用脱敏占位环境变量通过；Docker 用户配置读权限 warning 不影响 compose 解析 |
| `npm --prefix frontend run lint` | 通过 |
| `npm --prefix frontend run build` | 通过 |
| `git diff --check` | 通过；仅 CRLF 转换提示 |

## 安全与隐私边界

- 所有新增脚本默认只读，仅写入指定报告输出目录。
- 不删除用户数据。
- 不自动清理报告。
- 不修改 `.env`。
- 不读取或输出真实 secret 原文。
- 不输出 prompt 原文。
- 不执行真实外网 LLM。
- 默认不连接真实外部 IdP，不执行 OIDC token exchange。
- 审计与证据路径保持脱敏边界。

## 运维边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- `AUTH_ENABLED`、`RBAC_ENABLED`、`OIDC_ENABLED` 默认不启用。
- `storage_backend` 默认仍保留 sqlite 路径。
- v3.6 当前完成的是身份、权限、OIDC、租户归属和跨租户审计证据的设计与验收准备。
- release prep 不自动创建 tag 或 GitHub Release。

## 已知限制

- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC 完成。
- 不宣称多租户、复杂 BI 全量完成。
- 当前不改 JWT payload。
- 当前不迁移数据库。
- 当前不启用 tenant enforcement。
- 当前不修改 audit store schema。
- 真实外部 MCP Server、生产级 SSO/OIDC、多租户运行时隔离和复杂 BI 仍需后续专项验收。

## Go / No-Go

- **Go**：可进入 v3.6.0 tag 前最终复核。
- **No-Go**：本轮不打 tag，不创建 GitHub Release。
- **No-Go**：公网直上仍不允许。
- **Manual decision**：是否创建 `v3.6.0` tag 和 GitHub Release 需用户单独确认。

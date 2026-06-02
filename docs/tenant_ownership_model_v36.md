# v3.6 Phase 16.2 Tenant ownership model draft

## 目标

Phase 16.2 定义企业身份与租户边界的最小归属模型草案，用于统一后续数据库、API、JWT、RBAC、审计和跨租户拒绝证据的口径。

本阶段只提供草案模型和文档，不接入运行链路。

## 草案模型

草案 Pydantic 模型位于 `app/models/schemas.py`：

- `OrganizationScopeDraft`
- `TenantScopeDraft`
- `ProjectScopeDraft`
- `PrincipalScopeDraft`
- `RoleAssignmentDraft`
- `ResourceScopeDraft`
- `AuditScopeDraft`
- `TenantOwnershipModelDraft`

## 概念边界

| 概念 | 说明 | 当前状态 |
|------|------|----------|
| `organization` | 企业组织边界，承载一个或多个租户 | 草案模型已定义 |
| `tenant` | 租户边界，后续用于隔离用户、项目、资源、审计 | 草案模型已定义 |
| `project` | 租户下的项目或工作区边界 | 草案模型已定义 |
| `principal` | 用户或服务账号主体 | 草案模型已定义 |
| `role_assignment` | 主体在某个 scope 下的角色授权 | 草案模型已定义 |
| `resource_scope` | task/tool/audit/report 等资源的归属范围 | 草案模型已定义 |
| `audit_scope` | 审计事件需要携带的组织、租户、项目、资源与访问决策字段 | 草案模型已定义 |

## 字段归属建议

### 未来可进入 JWT 的 claim

- `organization_id`
- `tenant_id`
- `project_id`

这些字段只作为未来 claim 草案。当前 `TokenPayload` 不包含这些字段，本阶段不改 JWT payload。

### 建议由服务端 store 管理的字段

- `role_assignments`
- `resource_scope`
- `audit_scope`

这些字段不应完全信任客户端或 JWT。后续接入运行时 enforcement 时，应从服务端 store 读取并校验。

### 仅用于审计的字段

- `actor_principal_id`
- `resource_id`
- `decision`
- `denial_reason`

这些字段用于记录访问结果、拒绝原因和复核证据，不作为默认授权来源。

## 跨租户拒绝规则草案

- 主体访问资源时，必须满足主体 scope 与资源 scope 在 organization/tenant/project 层级上兼容。
- 若主体缺少资源 tenant 的有效 `role_assignment`，访问应拒绝。
- 若资源有 project scope，主体授权 scope 至少需要覆盖该 project 或其上级 tenant。
- 审计事件必须记录 allow/deny/not_evaluated 结果。
- deny 事件必须记录 `denial_reason`，后续用于 Phase 16.5 证据模板。

## 兼容策略

- 默认开发路径继续保持 `AUTH_ENABLED=false`、`RBAC_ENABLED=false`、`OIDC_ENABLED=false`。
- 现有 `User`、`TokenPayload`、`InMemoryUserStore` 行为不变。
- SQLite demo 数据和默认离线演示路径不变。
- 草案模型不触发数据库迁移。
- 草案模型不改变现有 API 响应结构。
- 后续启用 tenant enforcement 前，必须先完成迁移方案、拒绝路径测试、审计隔离测试和回滚方案。

## 不做什么

- 不迁移数据库。
- 不改现有 user store 行为。
- 不改 JWT payload。
- 不启用 tenant enforcement。
- 不连接真实 IdP。
- 不改变默认离线 demo。
- 不宣称生产级 SSO/OIDC 或多租户完成。

## 验证

```powershell
python -m pytest tests/test_tenant_ownership_model_v362.py -q
python -m pytest tests/test_identity_tenant_boundary_inventory_v361.py -q
python -m pytest tests/test_auth_v20.py tests/test_rbac_v20.py -q
docker compose config
```

## 后续衔接

- Phase 16.3：把 `ENDPOINT_PERMISSIONS` 导出为可审查 RBAC matrix。
- Phase 16.5：基于 `AuditScopeDraft` 建立跨租户拒绝与审计证据模板。

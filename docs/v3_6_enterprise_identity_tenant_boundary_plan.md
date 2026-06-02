# v3.6 Enterprise Identity & Tenant Boundary 规划

## 定位

- v3.6 = **Enterprise Identity & Tenant Boundary**。
- 核心目标：在 v3.5 已完成受控试点证据运营闭环后，进入企业身份、权限、租户边界和审计隔离的专项设计与验收准备。
- 当前仅进入规划阶段，版本保持 `3.5.0`。
- 本轮不改业务逻辑、不改版本号、不打 tag、不创建 GitHub Release。

## 现状基线

- `v3.5.0` GitHub Release 已创建，发布后检查见 `docs/post_release_check_v3.5.0.md`。
- 现有认证能力：
  - `app/auth/models.py` 已有 `UserRole`、`User`、`TokenPayload`、`LoginRequest`、`TokenResponse`、`UserInfo`。
  - `app/auth/jwt.py` 已支持 JWT access token 创建与解码。
  - `app/api/auth.py` 已支持 `/auth/login` 与 `/auth/me`。
  - `app/auth/dependencies.py` 已支持 `require_permission`、`require_roles` 与角色层级。
- 现有 RBAC 能力：
  - `ENDPOINT_PERMISSIONS` 已覆盖 tasks、approvals、audit、metrics、tools、eval、memory、reflection、snapshot 等关键权限。
  - `auth_enabled=false`、`rbac_enabled=false` 仍是默认离线路径。
- 现有 OIDC 能力：
  - `app/auth/oidc_config.py` 与 `/auth/oidc/status` 已提供最小配置预检与密钥存在性布尔状态。
  - 当前 OIDC 不执行真实 token exchange，不等于生产级 SSO/OIDC 完成。
- 现有缺口：
  - JWT payload 目前不包含 `tenant_id`、`org_id`、`project_id` 或资源归属字段。
  - 用户模型目前没有组织、租户、项目归属。
  - 当前没有 tenant/org/project/resource ownership 的统一模型。
  - 当前没有跨租户访问拒绝测试、审计租户隔离测试或 tenant-aware 权限矩阵。

## 基线与边界

- 默认路径继续保持 fake/offline。
- 默认 pytest/CI 不调用真实 LLM，不连接真实外部 IdP。
- 不默认启用 `AUTH_ENABLED`、`RBAC_ENABLED`、`OIDC_ENABLED`。
- 不提交真实密钥、API key、token、client_secret、JWT_SECRET、DATABASE_URL、REDIS_URL。
- 不读取或输出真实 secret 原文。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC 已完成。
- 不宣称多租户、复杂 BI 全量完成。
- 不在未完成隔离测试前开放多租户生产承诺。

## 阶段优先级

- P0：Phase 16.1、Phase 16.2。
- P1：Phase 16.3、Phase 16.4。
- P2：Phase 16.5、Phase 16.6。

## Phase 16.1：Identity and tenant boundary inventory（P0）

### 目标

建立只读身份与租户边界盘点，明确当前用户、角色、权限、OIDC、审计和资源归属的现状与缺口，形成后续实施的证据基线。

### 修改范围

- 新增身份与租户边界盘点 runbook，例如 `docs/identity_tenant_boundary_inventory_v36.md`。
- 可选新增只读脚本 `scripts/identity_tenant_boundary_inventory.py` 与测试。
- 盘点输入来自现有代码元数据、配置项、权限矩阵和测试文件，不读取真实 secret。
- 默认输出目录为 `docs/reports/identity_tenant_boundary/`。

### 不做什么

- 不改 JWT payload。
- 不新增真实租户 enforcement。
- 不连接真实 IdP。
- 不启用 auth/rbac/oidc 默认开关。
- 不宣称生产级 SSO/OIDC 或多租户完成。

### 验证命令

```powershell
python -m pytest tests/test_auth_v20.py tests/test_rbac_v20.py tests/test_oidc_config_v75.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
docker compose config
```

### 完成标准

- 输出当前身份模型、角色层级、权限矩阵、OIDC 配置预检、审计边界和资源归属缺口。
- 缺失 tenant/org/project/resource ownership 时记录为 `gap`，不得伪造成已完成。
- 输出明确 `read_only=true`、`real_idp_connected=false`、`tenant_enforcement_enabled=false`。

## Phase 16.2：Tenant ownership model draft（P0）

### 目标

形成组织、租户、项目、用户、角色和资源归属的最小模型草案，为后续数据库、API、审计和权限链路接入提供统一口径。

### 修改范围

- 新增模型设计文档，例如 `docs/tenant_ownership_model_v36.md`。
- 定义 `organization`、`tenant`、`project`、`principal`、`role_assignment`、`resource_scope`、`audit_scope` 等概念边界。
- 明确哪些字段未来进入 JWT，哪些字段来自服务端 store，哪些字段仅用于审计。
- 可选新增 Pydantic schema 草案，但不接入运行链路。

### 不做什么

- 不迁移数据库。
- 不改现有 user store 行为。
- 不把租户模型宣称为已启用。
- 不改变默认离线 demo。

### 验证命令

```powershell
python -m pytest tests/test_auth_v20.py tests/test_rbac_v20.py -q
docker compose config
```

### 完成标准

- 模型能解释用户、角色、组织、租户、项目、资源和审计记录之间的所有权关系。
- 明确跨租户拒绝规则和审计记录字段要求。
- 明确迁移前后兼容策略。

## Phase 16.3：RBAC matrix hardening（P1）

### 目标

把现有 `ENDPOINT_PERMISSIONS` 扩展为可审查、可导出的权限矩阵，并建立最小权限、权限申请、定期复核和拒绝证据口径。

### 修改范围

- 新增 RBAC 权限矩阵文档，例如 `docs/rbac_permission_matrix_v36.md`。
- 可选新增只读导出脚本 `scripts/rbac_permission_matrix.py` 与测试。
- 覆盖 admin/operator/viewer/auditor 对关键 API 的读写、审批、审计和工具调用边界。
- 保持现有默认 `rbac_enabled=false` 行为不变。

### 不做什么

- 不新增生产登录系统。
- 不绕过现有 `require_permission`。
- 不改变默认 API token 要求。
- 不宣称权限治理已生产完成。

### 验证命令

```powershell
python -m pytest tests/test_rbac_v20.py -q
python -m pytest tests/test_auth_v20.py -q
docker compose config
```

### 完成标准

- 权限矩阵可解释每类角色可执行和不可执行的关键动作。
- 拒绝路径包含 401/403 验收口径。
- 输出保留默认关闭边界。

## Phase 16.4：OIDC lifecycle drill plan（P1）

### 目标

把 OIDC 最小配置预检扩展为生产级联调前的生命周期演练计划，覆盖 token 生命周期、登出、JWKS 轮换、client_secret 轮换和失败路径。

### 修改范围

- 新增 OIDC 生命周期演练文档，例如 `docs/oidc_lifecycle_drill_v36.md`。
- 可选新增只读演练窗口脚本，复用既有 `live_drill_window` 和 `controlled_integration_dry_run` 输出。
- 明确真实 IdP 仅 opt-in，不进入默认测试和 CI。

### 不做什么

- 默认不连接真实 IdP。
- 默认不执行 token exchange。
- 不输出 client_secret 或 token 原文。
- 不宣称生产级 SSO/OIDC 已完成。

### 验证命令

```powershell
python -m pytest tests/test_oidc_config_v75.py tests/test_deployment_guard_v60.py -q
docker compose config
```

### 完成标准

- 缺少真实 IdP opt-in 条件必须记录为 `skipped`。
- 所有 secret 只输出 env name 与 present 布尔状态。
- 生命周期演练清楚区分配置预检、真实 IdP 联调和生产验收。

## Phase 16.5：Cross-tenant audit and denial evidence（P2）

### 目标

建立跨租户访问拒绝、审计隔离和脱敏导出的证据模板，为后续 tenant enforcement 接入前定义验收标准。

### 修改范围

- 新增跨租户拒绝与审计证据 runbook，例如 `docs/cross_tenant_audit_evidence_v36.md`。
- 可选新增只读证据汇总脚本，引用 audit export、RBAC matrix、tenant model 草案。
- 明确 audit event 未来需要包含的 tenant/org/project scope 字段。

### 不做什么

- 不改审计 store schema。
- 不生成伪造的跨租户通过证据。
- 不读取或输出 prompt 原文、密钥原文或连接串密码原文。

### 验证命令

```powershell
python -m pytest tests/test_audit_v045.py tests/test_audit_retention_export_v74.py -q
docker compose config
```

### 完成标准

- 证据模板能覆盖允许、拒绝、审计记录、导出脱敏和复核责任人。
- 明确哪些能力当前是规划/模板，哪些能力已由现有代码支持。

## Phase 16.6：v3.6 release prep（P2）

### 目标

完成 v3.6 release prep，同步版本号、release notes、release review 和 tag 决策前复核材料。

### 修改范围

- 将版本同步到 `3.6.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、脚本 version markers、相关测试断言。
- 新增 `RELEASE_NOTES_v3.6.0.md`。
- 新增 `docs/release_review_v3.6_enterprise_identity_tenant_boundary.md`。
- 更新 README、AGENTS、生产就绪清单和本规划文档。

### 不做什么

- release prep 当轮不打 tag。
- release prep 当轮不创建 GitHub Release。
- 不移动、删除或重建历史 tag。
- 不执行真实外网 LLM。
- 不宣称生产级 SSO/OIDC 或多租户全量完成。

### 验证命令

```powershell
python -m pytest -q
docker compose config
npm --prefix frontend run lint
npm --prefix frontend run build
```

### 完成标准

- release notes 覆盖 Phase 16.1~16.5、状态边界与默认 fake/offline 约束。
- release review 覆盖 scope、changed docs/scripts/tests/modules、verification matrix、security/privacy boundary、operational boundary、known limitations、Go/No-Go。
- 明确可进入 tag 决策前复核，但 release prep 当轮是否打 tag 需单独确认。

## 本轮规划验收

- 新增本规划文档。
- README、AGENTS、生产就绪清单记录 v3.6 规划入口。
- 本轮不改业务逻辑、不改版本号、不打 tag、不创建 Release。
- 本轮不执行真实外网 LLM，不连接真实 IdP。
- 默认 fake/offline 和默认 pytest/CI 不调用真实 LLM边界保持不变。

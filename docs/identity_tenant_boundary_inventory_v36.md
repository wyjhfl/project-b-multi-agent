# v3.6 Phase 16.1 Identity and tenant boundary inventory Runbook

## 目标

Phase 16.1 建立只读身份与租户边界盘点，用于梳理当前认证、RBAC、OIDC、审计和资源归属能力，明确进入企业身份与租户边界专项前的缺口。

## 入口

```powershell
python scripts/identity_tenant_boundary_inventory.py
```

可指定输出目录：

```powershell
python scripts/identity_tenant_boundary_inventory.py --output-dir docs/reports/identity_tenant_boundary/
```

默认输出：

- JSON：`docs/reports/identity_tenant_boundary/*_identity_tenant_boundary_inventory.json`
- Markdown：`docs/reports/identity_tenant_boundary/*_identity_tenant_boundary_inventory.md`

## 盘点范围

- 身份模型：`User`、`TokenPayload`、`UserRole`
- JWT：access token 创建与解码能力
- RBAC：`ROLE_HIERARCHY` 与 `ENDPOINT_PERMISSIONS`
- OIDC：配置键名、`/auth/oidc/status`、secret 布尔状态输出边界
- 审计：审计 API 与审计导出测试存在性
- 租户边界：organization、tenant、project、principal、role assignment、resource scope、audit scope 概念缺口

## 状态语义

- `success`：未发现身份、租户或审计边界缺口。
- `partial`：现有能力可盘点，但仍存在 tenant/org/project/resource ownership 或 enforcement 缺口。
- `skipped`：输入或本地上下文不足，无法形成盘点。
- `blocked`：发现只读边界或 secret 泄漏风险。
- `failed`：脚本执行失败或输出不可解释。

## 当前预期

当前阶段预期为 `partial`，原因是：

- `User` 模型尚无 tenant/org/project scope 字段。
- `TokenPayload` 尚无 tenant/org/project scope 字段。
- 尚无 organization/tenant/project/resource ownership 统一模型。
- 尚未启用跨租户访问拒绝的运行时 enforcement。
- 审计事件尚未定义 tenant/org/project scope 字段。

这些缺口必须记录为 `gap`，不得伪造成已完成。

## 只读边界

- 不读取 `.env` 或真实 secret 值。
- 不输出 token、client_secret、JWT_SECRET、DATABASE_URL 或 REDIS_URL 原文。
- 不连接真实外部 IdP。
- 不执行 OIDC token exchange。
- 不改 JWT payload。
- 不新增或启用 tenant enforcement。
- 不默认启用 `AUTH_ENABLED`、`RBAC_ENABLED`、`OIDC_ENABLED`。
- 不写业务数据。
- 不执行真实外网 LLM。
- 不宣称生产级 SSO/OIDC 已完成。
- 不宣称多租户、复杂 BI 全量完成。

## 验证

```powershell
python -m pytest tests/test_identity_tenant_boundary_inventory_v361.py -q
python -m pytest tests/test_auth_v20.py tests/test_rbac_v20.py tests/test_oidc_config_v75.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
docker compose config
```

## 后续衔接

- Phase 16.2：定义 tenant ownership model draft。
- Phase 16.3：RBAC matrix hardening。
- Phase 16.5：Cross-tenant audit and denial evidence。

# v3.6 Phase 16.3 RBAC permission matrix Runbook

## 目标

Phase 16.3 将现有 `ROLE_HIERARCHY` 与 `ENDPOINT_PERMISSIONS` 导出为可审查的 RBAC 权限矩阵，帮助企业试点评审 admin/operator/viewer/auditor 的最小权限边界、拒绝路径和复核流程。

本阶段只读导出矩阵，不改变鉴权逻辑。

## 入口

```powershell
python scripts/rbac_permission_matrix.py
```

可指定输出目录：

```powershell
python scripts/rbac_permission_matrix.py --output-dir docs/reports/rbac_permission_matrix/
```

默认输出：

- JSON：`docs/reports/rbac_permission_matrix/*_rbac_permission_matrix.json`
- Markdown：`docs/reports/rbac_permission_matrix/*_rbac_permission_matrix.md`

## 输入来源

- `app/auth/dependencies.py`
  - `ROLE_HIERARCHY`
  - `ENDPOINT_PERMISSIONS`
- `app/core/config.py`
  - `AUTH_ENABLED`
  - `RBAC_ENABLED`

## 输出字段

- `role_hierarchy`：角色层级展开结果。
- `permissions`：每个 permission 的 resource、action、risk、allowed_roles、denied_roles、role_matrix。
- `rejection_evidence`：401/403 验收口径。
- `review_process`：权限申请、定期复核和紧急授权流程说明。
- `boundary_declarations`：只读、默认关闭、不宣称生产级权限治理完成等边界。

## 最小权限口径

- `viewer` 只能访问读类能力，不能创建任务、调用工具、运行 eval、管理 snapshot。
- `operator` 可执行操作类能力，但不能读取或导出审计。
- `auditor` 可读取/导出审计并保留 viewer 读权限，但不能创建任务、审批或调用工具。
- `admin` 拥有当前全部角色能力，但后续 tenant scope enforcement 前仍需复核。

## 拒绝路径

- 未携带 token 或 token 无效：`401`。
- 已认证但角色不满足 permission：`403`。
- 后续 tenant-aware enforcement 接入后，应把 permission、role、scope 三者共同写入拒绝证据。

## 只读边界

- 不新增生产登录系统。
- 不绕过现有 `require_permission`。
- 不改变默认 API token 要求。
- 不默认启用 `AUTH_ENABLED` 或 `RBAC_ENABLED`。
- 不写业务数据。
- 不读取或输出真实 secret 原文。
- 不连接真实外部 IdP。
- 不执行真实外网 LLM。
- 不宣称权限治理已生产完成。
- 不宣称生产级 SSO/OIDC 或多租户完成。

## 验证

```powershell
python -m pytest tests/test_rbac_permission_matrix_v363.py -q
python -m pytest tests/test_rbac_v20.py tests/test_auth_v20.py -q
docker compose config
```

## 后续衔接

- Phase 16.4：OIDC lifecycle drill plan。
- Phase 16.5：Cross-tenant audit and denial evidence。

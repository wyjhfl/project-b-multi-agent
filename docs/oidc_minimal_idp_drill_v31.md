# v3.1 Phase 11.4：OIDC/SSO 最小真实 IdP 配置演练

## 1. 演练定位

- 本文档用于 **最小真实 IdP 配置演练**（runbook/checklist 级别）。
- 目标是验证配置边界与门禁行为，不包含完整登录跳转接入。
- **不等于生产级 SSO/OIDC 已完成**，不等于公网生产可直接上线。

## 2. 角色边界

支持角色仅限：

- `admin`
- `operator`
- `viewer`
- `auditor`

`OIDC_ALLOWED_ROLES` 必须是上述子集；`OIDC_DEFAULT_ROLE` 必须在 `OIDC_ALLOWED_ROLES` 中。

## 3. 配置项说明（占位示例）

- `OIDC_ENABLED`：是否启用 OIDC（默认 `false`）
- `OIDC_ISSUER_URL`：示例 `https://idp.example.com/realms/demo`
- `OIDC_CLIENT_ID`：示例 `project-b-console`
- `OIDC_CLIENT_SECRET_ENV`：示例 `OIDC_CLIENT_SECRET`（只配置环境变量名）
- `OIDC_REDIRECT_URI`：示例 `https://console.example.com/auth/callback`
- `OIDC_SCOPES`：示例 `openid,email,profile`
- `OIDC_ROLE_CLAIM`：示例 `roles`
- `OIDC_DEFAULT_ROLE`：示例 `viewer`
- `OIDC_ALLOWED_ROLES`：示例 `admin,operator,viewer,auditor`
- `OIDC_REQUIRE_HTTPS`：建议 `true`

> 禁止写入真实 `client_secret`。仅允许在部署环境注入 `OIDC_CLIENT_SECRET`。

## 4. development 与 production 差异

### development

- 允许 `localhost` / `127.0.0.1` 的 `http` issuer/redirect（仅 warning）。
- 仍建议使用 https 示例配置，避免上线前切换遗漏。

### production

- 启用 OIDC 时必须满足：
  - issuer/redirect 使用 `https`
  - `OIDC_CLIENT_SECRET_ENV` 非空
  - `OIDC_CLIENT_SECRET_ENV` 指向环境变量存在且非空
- deployment guard 对不满足项返回 `ok=false` 与结构化错误。

## 5. role claim 与 fallback 规则

- `OIDC_ROLE_CLAIM` 对应值可为：
  - 字符串（单角色）
  - 列表（多角色）
- 映射时仅保留 `OIDC_ALLOWED_ROLES` 范围内角色。
- 若 claim 缺失或无可用角色，回退到 `OIDC_DEFAULT_ROLE`。
- 若 `OIDC_DEFAULT_ROLE` 非法或不在允许列表，配置校验失败。

## 6. 检查步骤

### 6.1 `/auth/oidc/status`（只读状态检查）

1. 设置占位配置（不要填真实密钥值）：
   - `OIDC_ENABLED=true`
   - `OIDC_ISSUER_URL=https://idp.example.com/realms/demo`
   - `OIDC_CLIENT_ID=project-b-console`
   - `OIDC_CLIENT_SECRET_ENV=OIDC_CLIENT_SECRET`
   - `OIDC_REDIRECT_URI=https://console.example.com/auth/callback`
2. 在当前 shell 注入临时占位密钥环境变量（仅本地临时）：
   - `OIDC_CLIENT_SECRET=placeholder-secret-for-drill`
3. 请求：
   - `GET /auth/oidc/status`
4. 预期：
   - 返回 `client_secret_present=true`
   - 不返回 `client_secret` 原文
   - 返回 errors/warnings 仅为配置问题摘要

### 6.2 deployment guard 检查

1. 运行：
   - `GET /deployment/check`
2. 预期：
   - OIDC 配置不完整时：`ok=false`，含具体错误键
   - OIDC 配置合法时：OIDC 相关检查通过

## 7. 常见失败场景

- issuer 缺失：`OIDC_ISSUER_URL` 为空
- secret env 缺失：`OIDC_CLIENT_SECRET_ENV` 为空或未注入对应环境变量
- redirect 非 https（production）
- `OIDC_DEFAULT_ROLE` 不在 `OIDC_ALLOWED_ROLES`
- `OIDC_ALLOWED_ROLES` 包含非内置角色
- role claim 名称或内容不匹配，导致回退角色

## 8. 回滚步骤

1. 设置 `OIDC_ENABLED=false`
2. 清理临时环境变量（如 `OIDC_CLIENT_SECRET`）
3. 保留业务数据，不删除用户数据文件
4. 重新执行 `/auth/oidc/status` 与 `/deployment/check` 确认恢复

## 9. 边界声明

- 本文档不包含真实生产 IdP 对接凭据。
- 本阶段不实现完整 SSO 登录流程，不宣称生产级 SSO/OIDC 完成。
- 默认 fake/offline 与默认 pytest/CI 不调用真实 LLM 行为保持不变。


# v3.6 Phase 16.4 OIDC lifecycle drill plan

## 目标

Phase 16.4 把 OIDC 最小配置预检扩展为生产级联调前的生命周期演练计划，覆盖 token 生命周期、登出、JWKS 轮换、client_secret 轮换和失败路径。

本阶段只生成只读演练计划，不连接真实 IdP，不执行 token exchange。

## 入口

```powershell
python scripts/oidc_lifecycle_drill.py
```

可指定输出目录：

```powershell
python scripts/oidc_lifecycle_drill.py --output-dir docs/reports/oidc_lifecycle_drill/
```

默认输出：

- JSON：`docs/reports/oidc_lifecycle_drill/*_oidc_lifecycle_drill.json`
- Markdown：`docs/reports/oidc_lifecycle_drill/*_oidc_lifecycle_drill.md`

## 演练场景

- OIDC 配置预检
- Token 生命周期演练
- 登出与会话失效演练
- JWKS 轮换演练
- client_secret 轮换演练
- 失败路径演练

## 状态语义

- `skipped`：缺少真实 IdP opt-in 条件，必须列出 `missing_conditions`。
- `partial`：配置条件齐备，但本阶段仍未执行真实 token exchange，只能进入人工演练准备。
- `success`：保留给后续真实 IdP opt-in 演练完成后使用。
- `blocked`：发现 secret 原文、token 原文或只读边界被破坏。
- `failed`：脚本执行失败或输出不可解释。

## 只读边界

- 仅检查配置键、env name 与 present 布尔状态。
- 不输出 client_secret 或 token 原文。
- 默认不连接真实外部 IdP。
- 默认不执行 OIDC token exchange。
- 不修改 `.env` 或环境变量。
- 不默认启用 `AUTH_ENABLED`、`RBAC_ENABLED`、`OIDC_ENABLED`。
- 不写业务数据。
- 不执行真实外网 LLM。
- 缺少真实 IdP opt-in 条件时记录为 `skipped`。
- 不宣称生产级 SSO/OIDC 已完成。
- 不宣称多租户、复杂 BI 全量完成。

## 验证

```powershell
python -m pytest tests/test_oidc_lifecycle_drill_v364.py -q
python -m pytest tests/test_oidc_config_v75.py tests/test_deployment_guard_v60.py -q
docker compose config
```

## 后续衔接

- Phase 16.5：把 OIDC 拒绝路径、RBAC matrix 和 tenant model 草案纳入跨租户审计与拒绝证据模板。

# v3.2 Phase 12.4：Failure Diagnostics Pack（只读诊断）

## 1. 目标与定位

- 本文档用于企业内网试点/准生产演示阶段的常见失败快速诊断。
- 默认路径保持 fake/offline，不执行真实外网 LLM。
- 本文档与脚本只做只读检查，不写入/删除业务数据，不清理用户数据。

## 2. 快速入口

- 诊断脚本：`python scripts/failure_diagnostics.py`
- 自定义输出目录：`python scripts/failure_diagnostics.py --output-dir .tmp_failure_diagnostics_check`
- 默认输出目录：`docs/reports/failure_diagnostics/`
- 输出格式：JSON + Markdown

## 3. 覆盖场景（症状 → 检查点 → 处理建议）

### 3.1 `docker compose config` 失败

- 检查点：`docker compose config` 返回码与 stderr。
- 处理建议：修复 compose 语法或变量引用后重试。
- 恢复原则：不删除用户数据。

### 3.2 prod compose 缺 `JWT_SECRET` / `DATABASE_URL` / `REDIS_URL`

- 检查点：三项变量是否缺失或占位值。
- 处理建议：在部署环境注入真实值（不写入仓库），再执行 prod compose 校验。
- 恢复原则：不删除用户数据。

### 3.3 `/deployment/check` 出现 `ok=false`

- 检查点：offline deployment guard 与在线 `/deployment/check` 结果。
- 处理建议：按错误项逐条修复（CORS、安全头、限流、OIDC、审计脱敏等）后复测。
- 恢复原则：不删除用户数据。

### 3.4 `/operations` service unavailable

- 检查点：`/health` 不可达时，`/operations/summary` 标记 skipped/service_unavailable。
- 处理建议：先启动服务，再执行在线诊断。
- 恢复原则：不删除用户数据。

### 3.5 `demo_e2e` online smoke skipped

- 检查点：最近 `docs/reports/demo_artifacts/*/online_smoke_result.json` 的 `status/reason`。
- 处理建议：服务可用后重跑 `scripts/demo_e2e.ps1`；离线演示可保留 skipped 记录。
- 恢复原则：不删除用户数据。

### 3.6 acceptance snapshot online checks skipped

- 检查点：最近 `docs/reports/acceptance_snapshots/*_acceptance_snapshot.json` 的 `online_checks.status`。
- 处理建议：服务可用后重跑 `scripts/acceptance_snapshot.py` 生成在线补充快照。
- 恢复原则：不删除用户数据。

### 3.7 pilot reports 为空

- 检查点：pilot report 目录是否存在、报告数量是否为 0。
- 处理建议：先执行离线 demo seed；真实 LLM 仅在 opt-in 环境齐全时补充报告。
- 恢复原则：不删除用户数据。

### 3.8 audit export 返回 403 `audit_export_redaction_required`

- 检查点：`/audit/events/export` 返回 403 且错误码为 `audit_export_redaction_required`。
- 处理建议：启用 `AUDIT_EXPORT_REDACTION_ENABLED=true`，确保导出始终脱敏。
- 恢复原则：不删除用户数据。

### 3.9 OIDC `client_secret` 环境变量缺失

- 检查点：OIDC 启用时 `validate_oidc_settings()` 返回 `<ENV_NAME> 未注入或为空`。
- 处理建议：在部署环境注入 secret 对应环境变量；不要提交到仓库。
- 恢复原则：不删除用户数据。

### 3.10 real LLM opt-in skipped

- 检查点：`REAL_LLM_*` 必需变量或 `REAL_LLM_API_KEY_ENV` 指向 key 缺失。
- 处理建议：变量不齐全时保持 skipped；齐全后再手动执行 opt-in smoke。
- 恢复原则：不删除用户数据。

## 4. 诊断脚本行为说明

- 脚本只读取本地状态、环境变量和只读 API，不修改配置，不删除数据。
- 服务未启动时在线检查标记 skipped，不误报 success。
- 输出经过脱敏：
  - 不输出 prompt/query/raw_prompt/sql_prompt 原文；
  - 不输出 API key/token/client_secret/password/JWT_SECRET/DATABASE_URL/REDIS_URL 明文；
  - DSN 密码保持脱敏。

## 5. 边界声明

- 不等于公网生产直接上线。
- 不等于真实 LLM 生产验收完成。
- 不等于生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。

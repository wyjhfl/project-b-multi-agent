# v3.1 Phase 11.5：运维排障索引

## 1. 快速入口（只读优先）

- `/health`
- `/deployment/check`
- `/operations`
- `/metrics/runtime`
- `/audit/events/export`
- `/llm/pilot/reports`
- `/auth/oidc/status`

建议排障顺序：

1. 先看 `/health` 与容器状态；
2. 再看 `/deployment/check` 是否 `ok=false`；
3. 再看 `/operations` 聚合摘要；
4. 最后按专项接口排查（metrics/audit/pilot/oidc）。

---

## 2. 常见症状 → 检查点 → 处理建议

### 2.1 服务未启动

- 检查点：
  - `docker ps`
  - `docker compose logs app frontend --tail=200`
  - `GET /health`
- 处理建议：
  - 使用 `docker compose up -d app frontend` 启动；
  - 若镜像异常先 `docker compose build app frontend` 后重启。
- 恢复原则：
  - **不删除用户数据**，不执行破坏性清理。

### 2.2 `docker compose config` 失败

- 检查点：
  - `docker compose config` 输出错误位置；
  - `.env` 与 compose 文件语法。
- 处理建议：
  - 修复语法/变量引用后重试；
  - 优先使用 `.env.example` 对照缺项。
- 恢复原则：
  - **不删除用户数据**，仅修正配置。

### 2.3 prod compose 缺变量失败

- 检查点：
  - `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`
  - 缺失：`JWT_SECRET` / `DATABASE_URL` / `REDIS_URL`
- 处理建议：
  - 在当前 shell 注入临时演练变量后重试；
  - 演练结束清理临时环境变量。
- 恢复原则：
  - **不删除用户数据**，不删除卷。

### 2.4 deployment check `ok=false`

- 检查点：
  - `GET /deployment/check` 的 `errors[]` 与 `checks[]`
  - 重点关注：auth/rbac、CORS、security headers、rate limit、OIDC、audit retention。
- 处理建议：
  - 按错误键逐项修正配置；
  - 修复后再次执行 `/deployment/check`。
- 恢复原则：
  - **不删除用户数据**，只修配置。

### 2.5 `/operations` 无数据

- 检查点：
  - `/operations/summary` 是否可访问；
  - `task_approval`、`audit`、`pilot_reports` 字段是否为空；
  - 本地是否已执行 demo seed。
- 处理建议：
  - 执行 `python scripts/demo_seed_data.py` 准备演示数据；
  - 未启动服务时先启动服务再看在线摘要。
- 恢复原则：
  - **不删除用户数据**，仅补充演示数据或重启服务。

### 2.6 `demo_e2e` online smoke skipped

- 检查点：
  - `scripts/demo_e2e.ps1` 输出是否为 `service_unavailable`。
- 处理建议：
  - 先启动 `app/frontend` 容器，再重跑脚本；
  - 若仅离线演示，可接受 skipped 并记录说明。
- 恢复原则：
  - **不删除用户数据**。

### 2.7 pilot reports 为空

- 检查点：
  - `docs/reports/real_llm_pilot/` 目录是否存在；
  - 是否配置 `REAL_LLM_PILOT_REPORT_DIR`；
  - `/llm/pilot/reports` 返回是否为空列表。
- 处理建议：
  - 演示场景先执行 demo seed 生成脱敏示例报告；
  - 真实 LLM 场景必须先满足 opt-in 条件再执行 smoke。
- 恢复原则：
  - **不删除用户数据**，报告目录清理前先备份。

### 2.8 audit export 403 `audit_export_redaction_required`

- 检查点：
  - `AUDIT_EXPORT_ENABLED`
  - `AUDIT_EXPORT_REDACTION_ENABLED`
- 处理建议：
  - 确保导出红线开启：`AUDIT_EXPORT_REDACTION_ENABLED=true`；
  - 仅在脱敏开启后导出 JSONL。
- 恢复原则：
  - **不删除用户数据**，只修导出策略配置。

### 2.9 OIDC secret env 缺失

- 检查点：
  - `/auth/oidc/status` 中 `client_secret_present`
  - `/deployment/check` 中 `oidc_client_secret_present`
- 处理建议：
  - 确认 `OIDC_CLIENT_SECRET_ENV` 指向变量名；
  - 在部署环境注入对应 secret env（不写入仓库）。
- 恢复原则：
  - **不删除用户数据**，仅修 OIDC 环境配置。

### 2.10 真实 LLM opt-in skipped

- 检查点：
  - `REAL_LLM_SMOKE_ENABLED`
  - `REAL_LLM_ACCEPTANCE_ENABLED`
  - `REAL_LLM_PREFLIGHT_ENABLED`
  - `REAL_LLM_PREFLIGHT_NETWORK_CHECK`
  - `REAL_LLM_MODEL`
  - `REAL_LLM_API_KEY_ENV` 及其指向变量
- 处理建议：
  - 缺失任一变量时保持 skipped，不伪造成功；
  - 条件齐全后再手动执行 `scripts/real_llm_smoke.ps1`。
- 恢复原则：
  - **不删除用户数据**，不输出密钥原文。

---

## 3. 通用恢复原则

- 先备份、后调整、再验证；
- 禁止破坏性清理命令作为默认处理路径；
- 所有演练/排障动作默认遵循：**不删除用户数据**；
- 变更后至少复核：`/health`、`/deployment/check`、`docker compose config`。

## 4. 边界声明

- 默认 fake/offline，不执行真实外网 LLM。
- 不提交任何密钥、token、client_secret、数据库/Redis 密码。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。


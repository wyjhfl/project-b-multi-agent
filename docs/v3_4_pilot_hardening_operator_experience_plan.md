# v3.4 Pilot Hardening & Operator Experience 规划

## 定位

- v3.4 = **Pilot Hardening & Operator Experience**。
- 核心目标：围绕企业内网试点硬化、操作员体验、故障恢复演练、证据归档索引、可选真实集成预检增强推进。
- 当前阶段仅做路线规划与入口收口，不改业务逻辑、不改版本号、不打 tag、不创建 GitHub Release。
- 当前版本保持 `3.3.0`，直到 v3.4 release prep 阶段才同步为 `3.4.0`。

## 基线与边界

- `v3.3.0` GitHub Release 已由用户手动创建，历史 tag 保持不变。
- 默认路径继续保持 fake/offline，默认 pytest/CI 不调用真实外网 LLM。
- 缺少 opt-in 条件时必须记录为 `skipped`，不得伪造成成功。
- 不提交真实密钥、API key、token、client_secret、JWT_SECRET、DATABASE_URL、REDIS_URL。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。

## 阶段优先级

- P0：Phase 14.1、Phase 14.2。
- P1：Phase 14.3、Phase 14.4。
- P2：Phase 14.5、Phase 14.6。

## Phase 14.1：Operator workflow polish（P0）

### 目标

优化操作员日常入口、runbook 链接、状态解释与只读运维证据导航，让 `/operations`、快照、诊断、治理与演练产物更容易被发现和串联。

### 修改范围

- 新增或更新操作员工作流文档，例如 `docs/operator_workflow_polish_v34.md`。
- 可选新增只读索引脚本 `scripts/operator_workflow_index.py` 与对应测试。
- 更新 `README.md`、`AGENTS.md`、`docs/production_readiness_checklist.md` 和本规划文档中的 Phase 14.1 状态。
- 可选小幅更新前端 `/operations` 只读入口，但仅限低风险、可测试的导航与状态说明。

### 不做什么

- 不做复杂前端重构。
- 不新增写入、删除、自动清理或业务数据修改能力。
- 不修改 `.env`。
- 不调用真实外网 LLM。
- 不改变 auth/RBAC 默认关闭边界。

### 验证命令

```powershell
python -m pytest tests/test_operator_workflow_index_v341.py -q
python -m pytest tests/test_operations_automation_scripts_v334.py tests/test_runtime_hardening_v055.py -q
python -m pytest -q
docker compose config
```

如涉及前端：

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
```

### 完成标准

- 操作员入口覆盖 `/operations`、acceptance snapshot、demo artifact bundle、failure diagnostics、report index、config drift、governance summary、live drill window。
- 每个入口说明使用时机、默认输出目录、是否只读、是否调用真实 LLM、失败或 skipped 状态解释。
- 只读边界清晰：不删除数据、不自动清理报告、不修改 `.env`、不执行真实外网 LLM。
- 本阶段交付物已落地：`docs/operator_workflow_polish_v34.md`、`scripts/operator_workflow_index.py`、`tests/test_operator_workflow_index_v341.py`。

## Phase 14.2：Incident rehearsal pack（P0）

### 目标

建立只读故障演练包，把常见企业内网试点故障转为可重复演练、可归档证据、可解释 `skipped` / `blocked` / `partial` 的流程。

### 修改范围

- 新增 `docs/incident_rehearsal_pack_v34.md`。
- 新增 `scripts/incident_rehearsal_pack.py` 与 `tests/test_incident_rehearsal_pack_v342.py`。
- 更新 `README.md`、`AGENTS.md`、`docs/production_readiness_checklist.md` 和本规划文档中的 Phase 14.2 状态。
- 覆盖服务不可用、compose 配置失败、prod compose 缺少必需环境变量、`/deployment/check` 返回 `ok=false`、`/operations` 不可用或为空、在线 smoke skipped、config drift warnings、OIDC/real LLM opt-in 缺失等场景。

### 不做什么

- 默认不启动服务。
- 不修改环境变量或 `.env` 文件。
- 不执行真实外网 LLM。
- 不做破坏性修复、数据删除或自动清理。

### 验证命令

```powershell
python -m pytest tests/test_incident_rehearsal_pack_v342.py -q
python scripts/incident_rehearsal_pack.py --output-dir .tmp_incident_rehearsal_check
Remove-Item -Recurse -Force .tmp_incident_rehearsal_check
python -m pytest tests/test_failure_diagnostics_v324.py tests/test_live_drill_window_v335.py -q
python -m pytest -q
docker compose config
```

如涉及前端：

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
```

### 完成标准

- 输出包含 `generated_at`、`commit`、`version`、`mode`、`read_only`、`real_llm_executed`、`scenarios`、`recommended_runbooks`、`missing_conditions`、`status`、`boundary_declarations`、`output_dir`。
- 状态词限定并解释为 `success`、`skipped`、`blocked`、`partial`、`failed`。
- 缺少 opt-in 条件时明确 `skipped`，不伪造成成功。
- 本阶段交付物已落地：`docs/incident_rehearsal_pack_v34.md`、`scripts/incident_rehearsal_pack.py`、`tests/test_incident_rehearsal_pack_v342.py`。

## Phase 14.3：Evidence archive manifest（P1）

### 目标

统一列出并索引所有试点证据产物，形成只读 manifest，便于交接、审计和 release review 使用。

### 修改范围

- 新增 `docs/evidence_archive_manifest_v34.md`。
- 新增 `scripts/evidence_archive_manifest.py` 与 `tests/test_evidence_archive_manifest_v343.py`。
- 更新 `README.md`、`AGENTS.md`、`docs/production_readiness_checklist.md` 和本规划文档中的 Phase 14.3 状态。
- 纳入 acceptance snapshots、demo artifacts、failure diagnostics、report index、config drift、governance policy、live drill window、incident rehearsal、release review / post release handoff 文档。

### 不做什么

- 不删除文件。
- 不自动执行 retention 清理。
- 不读取或输出 secret 原文。
- 不改业务数据。

### 验证命令

```powershell
python -m pytest tests/test_evidence_archive_manifest_v343.py -q
python scripts/evidence_archive_manifest.py --output-dir .tmp_evidence_manifest_check
Remove-Item -Recurse -Force .tmp_evidence_manifest_check
python -m pytest tests/test_report_index_v331.py tests/test_incident_rehearsal_pack_v342.py -q
python -m pytest -q
docker compose config
```

如涉及前端：

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
```

### 完成标准

- 输出包含 `generated_at`、`commit`、`version`、`manifest_id`、`evidence_roots`、`evidence_items`、`latest_by_type`、`missing_expected_types`、`total_files`、`total_size_bytes`、`retention_policy`、`boundary_declarations`、`read_only`、`real_llm_executed`。
- 支持 `--output-dir`。
- 空目录或缺失目录可解释为 `skipped` 或 warning，不报假成功。
- 本阶段交付物已落地：`docs/evidence_archive_manifest_v34.md`、`scripts/evidence_archive_manifest.py`、`tests/test_evidence_archive_manifest_v343.py`。

## Phase 14.4：Optional integration readiness matrix（P1）

### 目标

建立可选真实集成准备度矩阵，只做只读预检，不执行真实集成，用于判断真实 LLM、OIDC、外部 MCP、Postgres/Redis、前端构建网络依赖等是否具备演练条件。

### 修改范围

- 新增 `docs/optional_integration_readiness_matrix_v34.md`。
- 新增 `scripts/optional_integration_readiness.py` 与 `tests/test_optional_integration_readiness_v344.py`。
- 更新 `README.md`、`AGENTS.md`、`docs/production_readiness_checklist.md` 和本规划文档中的 Phase 14.4 状态。
- 覆盖 real LLM opt-in、OIDC、external MCP、Postgres、Redis、frontend build/network dependency、deployment guard、audit export/redaction readiness。

### 不做什么

- 不读取真实 secret 值，仅输出 env name 与 `present=true/false`。
- 不调用真实外网 LLM。
- 不连接真实外部 MCP，除非使用已有 fake/offline fixture。
- 不要求默认配置启用 auth、RBAC、Redis 或 PostgreSQL。

### 验证命令

```powershell
python -m pytest tests/test_optional_integration_readiness_v344.py -q
python scripts/optional_integration_readiness.py --output-dir .tmp_optional_integration_check
Remove-Item -Recurse -Force .tmp_optional_integration_check
python -m pytest tests/test_config_drift_v332.py tests/test_live_drill_window_v335.py -q
python -m pytest -q
docker compose config
```

如涉及前端：

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
```

### 完成标准

- 输出包含 `generated_at`、`commit`、`version`、`integrations`、`readiness_status`、`missing_conditions`、`skipped_reasons`、`risk_notes`、`recommended_next_actions`、`boundary_declarations`、`read_only`、`real_llm_executed`。
- 缺少真实 opt-in 条件时明确 `skipped`。
- 不输出任何 secret 原文。
- 本阶段交付物已落地：`docs/optional_integration_readiness_matrix_v34.md`、`scripts/optional_integration_readiness.py`、`tests/test_optional_integration_readiness_v344.py`。

## Phase 14.5：Pilot handoff checklist polish（P2）

### 目标

面向企业内网试点交接，整理角色、权限、恢复步骤、验收证据、已知限制与下一步决策。

### 修改范围

- 新增 `docs/pilot_handoff_checklist_v34.md`。
- 可选新增只读生成脚本 `scripts/pilot_handoff_checklist.py` 与测试。
- 更新 `README.md`、`AGENTS.md`、`docs/production_readiness_checklist.md` 和本规划文档中的 Phase 14.5 状态。
- 覆盖 admin/operator/viewer/auditor 角色、RBAC 边界、OIDC 最小演练边界、real LLM opt-in skipped/ready 解释、incident rehearsal、evidence archive manifest、optional integration readiness、backup/restore/checklist 链接与 known limitations。

### 不做什么

- 不实现生产登录系统。
- 不宣称生产级 SSO/OIDC 已完成。
- 不宣称公网生产可直接上线。
- 不把真实 LLM opt-in smoke 等同于生产验收。

### 验证命令

```powershell
python -m pytest tests/test_pilot_handoff_checklist_v345.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
python -m pytest -q
docker compose config
```

如涉及前端：

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
```

### 完成标准

- Go/No-Go 结论清晰：企业内网试点可继续，公网直上 No-Go，真实生产验收需另行执行。
- 交接清单可直接指向演练、证据归档、可选集成准备度与备份恢复文档。
- 已知限制与默认关闭边界明确。

## Phase 14.6：v3.4.0 release prep（P2）

### 目标

完成 v3.4.0 release prep，包括版本同步、release notes/review、验证矩阵、tag 决策前复核；本规划阶段不执行该阶段。

### 修改范围

- 版本同步：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、脚本 version 字段、相关测试断言。
- 新增 `RELEASE_NOTES_v3.4.0.md`。
- 新增 `docs/release_review_v3.4_pilot_hardening_operator_experience.md`。
- 更新 `README.md`、`AGENTS.md`、`docs/deployment_runbook.md`、`docs/production_readiness_checklist.md` 和本规划文档。
- 汇总 Phase 14.1~14.5 的验证矩阵与边界声明。

### 不做什么

- release prep 阶段不创建 tag。
- release prep 阶段不创建 GitHub Release。
- 不移动历史 tag。
- 不执行真实外网 LLM。

### 验证命令

```powershell
python -m pytest tests/test_operator_workflow_index_v341.py tests/test_incident_rehearsal_pack_v342.py -q
python -m pytest tests/test_evidence_archive_manifest_v343.py tests/test_optional_integration_readiness_v344.py -q
python -m pytest tests/test_pilot_handoff_checklist_v345.py -q
python -m pytest tests/test_operations_summary_v312.py tests/test_runtime_hardening_v055.py tests/test_mcp_stdio_client_v31.py -q
python -m pytest -q
docker compose config
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

如涉及前端：

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
```

### 完成标准

- 所有版本号同步为 `3.4.0`，且相关测试断言已更新。
- release notes 覆盖 Phase 14.1~14.5、状态边界与默认 fake/offline 约束。
- release review 覆盖 scope、changed docs/scripts/tests/modules、verification matrix、security/privacy boundary、operational boundary、known limitations、Go/No-Go。
- 明确可进入 tag 决策前复核，但本轮不打 tag、不创建 GitHub Release。

## 当前规划阶段完成标准

- 本文件存在并覆盖 Phase 14.1~14.6。
- `README.md`、`AGENTS.md`、`docs/production_readiness_checklist.md` 提供 v3.4 规划入口。
- 本轮不改业务逻辑、不改版本号、不打 tag、不创建 Release。
- 本轮验证通过：

```powershell
python -m pytest tests/test_runtime_hardening_v055.py -q
docker compose config
```

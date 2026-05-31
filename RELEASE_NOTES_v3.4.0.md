# v3.4.0 发布说明

## 摘要

v3.4.0 = **Pilot Hardening & Operator Experience**。

本轮 release prep 汇总 Phase 14.1~14.5 的企业内网试点硬化、操作员体验、故障演练、证据归档、可选集成准备度与交接清单能力。

## 阶段覆盖

### Phase 14.1 - 操作员工作流收口

- 新增 `docs/operator_workflow_polish_v34.md`。
- 新增 `scripts/operator_workflow_index.py` 和 `tests/test_operator_workflow_index_v341.py`。
- 统一 `/operations`、acceptance snapshot、demo artifact bundle、failure diagnostics、report index、config drift、governance summary、live drill window 的操作员入口说明。
- 保持只读边界，不删除数据、不自动清理报告、不修改 `.env`。

### Phase 14.2 - 故障演练包

- 新增 `docs/incident_rehearsal_pack_v34.md`。
- 新增 `scripts/incident_rehearsal_pack.py` 和 `tests/test_incident_rehearsal_pack_v342.py`。
- 覆盖服务不可用、compose/prod compose、deployment check、operations、acceptance/demo skipped、failure diagnostics、report index、config drift、governance/live drill、OIDC secret env、real LLM opt-in 缺失等场景。
- 状态词限定为 `success / skipped / blocked / partial / failed`。

### Phase 14.3 - 证据归档 Manifest

- 新增 `docs/evidence_archive_manifest_v34.md`。
- 新增 `scripts/evidence_archive_manifest.py` 和 `tests/test_evidence_archive_manifest_v343.py`。
- 统一索引 acceptance、demo、failure、report index、config drift、governance、live drill、operator workflow、incident rehearsal、release review、post release handoff 证据。
- 只记录文件元数据，不读取报告内容，不删除文件，不自动执行 retention 清理。

### Phase 14.4 - 可选集成准备度矩阵

- 新增 `docs/optional_integration_readiness_matrix_v34.md`。
- 新增 `scripts/optional_integration_readiness.py` 和 `tests/test_optional_integration_readiness_v344.py`。
- 覆盖真实 LLM、OIDC、外部 MCP、Postgres、Redis、前端 build/network dependency、deployment guard、audit export/redaction readiness。
- 仅输出 env name 与 `present=true/false`，不读取或输出真实 secret 值。

### Phase 14.5 - 企业内网试点交接清单

- 新增 `docs/pilot_handoff_checklist_v34.md`。
- 新增 `scripts/pilot_handoff_checklist.py` 和 `tests/test_pilot_handoff_checklist_v345.py`。
- 覆盖 admin/operator/viewer/auditor、RBAC 边界、OIDC 最小演练边界、real LLM skipped/ready 解释、演练与证据归档引用、备份恢复链接、已知限制。
- Go/No-Go：企业内网试点可继续，公网直上 No-Go，真实生产验收需另行执行。

## 边界声明

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 不执行真实外网 LLM。
- 不提交真实密钥、API key、token、client_secret、JWT_SECRET、DATABASE_URL、REDIS_URL。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- 本轮 release prep 不创建 tag，不创建 GitHub Release。

## 验证

- `python -m pytest -q`
- `docker compose config`
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`
- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`

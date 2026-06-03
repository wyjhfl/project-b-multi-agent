# v3.6 Phase 16.5 Cross-tenant audit and denial evidence

## 目标

Phase 16.5 建立跨租户访问拒绝、审计隔离和脱敏导出的证据模板，为后续 tenant enforcement 接入前定义验收标准。

本阶段只生成证据模板和元数据汇总，不修改审计存储结构，不启用 tenant enforcement，不生成伪造的跨租户通过证据。

## 入口

```powershell
python scripts/cross_tenant_audit_evidence.py
```

可指定输入和输出目录：

```powershell
python scripts/cross_tenant_audit_evidence.py `
  --rbac-matrix docs/reports/rbac_permission_matrix/example.json `
  --tenant-model-doc docs/tenant_ownership_model_v36.md `
  --audit-export-sample docs/reports/audit_export/example.json `
  --output-dir docs/reports/cross_tenant_audit_evidence/
```

默认输出：

- JSON：`docs/reports/cross_tenant_audit_evidence/*_cross_tenant_audit_evidence.json`
- Markdown：`docs/reports/cross_tenant_audit_evidence/*_cross_tenant_audit_evidence.md`

## 输入来源

- RBAC matrix JSON：来自 Phase 16.3 的 `scripts/rbac_permission_matrix.py` 输出，仅消费状态、版本、permission_count、denied_pair_count 等元数据。
- Tenant model 文档：来自 Phase 16.2 的 `docs/tenant_ownership_model_v36.md`，只记录文件存在性和元信息，不读取正文用于输出。
- Audit export sample JSON：用于验证脱敏边界的结构化样例。若发现 prompt、token、secret、连接串密码等敏感原文，状态必须为 `blocked`，且输出不得包含原文。

## 证据模板

- `allow_evidence`：同租户或授权 scope 内允许访问的证据要求。
- `deny_evidence`：跨租户、跨项目或权限不足时的拒绝证据要求。
- `audit_record_evidence`：未来 audit event 必须携带的 scope 字段要求。
- `export_redaction_evidence`：审计导出字段白名单和 detail 脱敏证据。
- `reviewer_owner_evidence`：拒绝、例外和复核责任人证据。

## 必需 audit scope 字段

- `organization_id`
- `tenant_id`
- `project_id`
- `resource_id`
- `actor_principal_id`
- `decision`
- `denial_reason`

## 拒绝用例

- 跨租户资源读取拒绝：`actor.tenant_id != resource.tenant_id`，预期 `403`。
- 跨项目资源写入拒绝：`actor.project_id not in resource.allowed_project_ids`，预期 `403`。
- 缺失 scope claim 拒绝：JWT 或服务端 principal 缺少 tenant/org/project scope，预期 `403`。
- 审计导出未启用脱敏拒绝：redaction disabled 时预期 `403`。

## 只读边界

- 不修改 audit store schema。
- 不生成伪造的跨租户通过证据。
- 不启用 tenant enforcement。
- 不改 JWT payload。
- 不写业务数据。
- 不修改 `.env` 或环境变量。
- 不读取或输出 prompt 原文、secret 原文、token 原文或连接串密码原文。
- 不执行真实外网 LLM。
- 不连接真实外部 IdP。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收完成。
- 不宣称生产级 SSO/OIDC 或多租户完成。

## 验证

```powershell
python -m pytest tests/test_cross_tenant_audit_evidence_v365.py -q
python -m pytest tests/test_audit_v045.py tests/test_audit_retention_export_v74.py -q
docker compose config
```

## 后续衔接

- Phase 16.6：v3.6 release prep。release prep 可引用本模板说明 Phase 16.1~16.5 的身份、权限、OIDC、租户归属和审计拒绝证据边界。
- 后续真正接入 tenant enforcement 前，必须另行实施 schema 迁移、JWT/server-side scope 接入、跨租户拒绝运行时测试和审计隔离测试。

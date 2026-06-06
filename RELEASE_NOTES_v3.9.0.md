# Project B v3.9.0 - Compliance Security Hardening

## 定位

v3.9.0 聚焦 Compliance Security Hardening，面向企业合规、安全治理和发布门禁，补齐上线前的审计、权限、密钥、数据、变更、回滚和安全测试证据。该版本仍保持默认 fake/offline，默认测试与 CI 不调用真实 LLM，不连接真实外部 MCP、业务系统、PostgreSQL、Redis、IdP、APM、日志平台、告警平台、KMS、Vault 或云平台。

## 交付范围

- Phase 19.1：Compliance security baseline inventory
  - `docs/compliance_security_baseline_v39.md`
  - `scripts/compliance_security_baseline.py`
  - `tests/test_compliance_security_baseline_v391.py`
- Phase 19.2：Secret rotation and leakage response pack
  - `docs/secret_rotation_leakage_response_pack_v39.md`
  - `scripts/secret_rotation_leakage_response_pack.py`
  - `tests/test_secret_rotation_leakage_response_pack_v392.py`
- Phase 19.3：Release gate and rollback governance pack
  - `docs/release_gate_rollback_governance_pack_v39.md`
  - `scripts/release_gate_rollback_governance_pack.py`
  - `tests/test_release_gate_rollback_governance_pack_v393.py`
- Phase 19.4：Security regression and compliance evidence pack
  - `docs/security_regression_compliance_evidence_pack_v39.md`
  - `scripts/security_regression_compliance_evidence_pack.py`
  - `tests/test_security_regression_compliance_evidence_pack_v394.py`
- Phase 19.5：v3.9.0 release prep
  - 版本同步到 `3.9.0`
  - `docs/release_review_v3.9_compliance_security_hardening.md`

## 边界

- 不启动服务作为新增脚本默认行为。
- 不访问在线端点。
- 不连接真实 IdP、KMS、Vault、云平台、LLM provider、外部 MCP、数据库、Redis、APM、日志平台、告警平台或业务系统。
- 不执行真实安全扫描、红队测试、审计导出、密钥创建/轮换/撤销、权限变更、发布、回滚、迁移或外部系统调用。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- 缺少 opt-in、正式签核或演练证据时记录为 `skipped`，不得伪造成 `success`。

## 未完成项

- 企业级安全扫描、红队测试、外部合规审计和正式安全签核尚未完成。
- 真实密钥轮换、泄漏响应、撤销恢复和 KMS/Vault 接入验收尚未完成。
- 真实发布签核、变更审批、回滚演练和生产发布门禁验收尚未完成。
- 公网生产直上、真实 LLM 生产验收、生产级 SSO/OIDC、多租户、复杂 BI、企业级 SRE/DR/容量验收仍不宣称完成。

## 验证

```powershell
python -m pytest tests/test_compliance_security_baseline_v391.py tests/test_secret_rotation_leakage_response_pack_v392.py tests/test_release_gate_rollback_governance_pack_v393.py tests/test_security_regression_compliance_evidence_pack_v394.py -q
python -m pytest tests/test_security_v04.py tests/test_guardrails_v44.py tests/test_guardrails_pii_leak_v44.py tests/test_security_headers_v71.py tests/test_request_guards_v72.py tests/test_auth_v20.py tests/test_rbac_v20.py tests/test_cross_tenant_audit_evidence_v365.py tests/test_audit_v045.py tests/test_audit_retention_export_v74.py tests/test_deployment_guard_v60.py -q
python -m pytest tests/test_runtime_hardening_v055.py tests/test_operations_summary_v312.py tests/test_mcp_stdio_client_v31.py tests/test_compliance_security_baseline_v391.py tests/test_secret_rotation_leakage_response_pack_v392.py tests/test_release_gate_rollback_governance_pack_v393.py tests/test_security_regression_compliance_evidence_pack_v394.py -q
python -m pytest -q
git diff --check
```

- v3.9 聚焦验证：56 passed, 2 warnings。
- v3.9 安全/合规回归：161 passed, 2 warnings。
- 全量回归：920 passed, 4 skipped, 2 warnings。
- `git diff --check`：通过，仅 CRLF 提示。

本轮 release prep 不打 `v3.9.0` tag，不创建 GitHub Release，不移动历史 tag。

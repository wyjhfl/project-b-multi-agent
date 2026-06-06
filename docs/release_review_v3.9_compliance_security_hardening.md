# v3.9.0 Release Review - Compliance Security Hardening

## Scope

v3.9.0 纳入 Phase 19.1~19.4 的合规安全基线、密钥轮换与泄漏响应、发布门禁与回滚治理、安全回归与合规证据包，并完成 Phase 19.5 release prep。目标是形成企业内网试点上线前的只读安全治理证据基线，不执行真实外部系统操作。

## Changed Files

- 文档：
  - `RELEASE_NOTES_v3.9.0.md`
  - `docs/v3_9_compliance_security_hardening_plan.md`
  - `docs/compliance_security_baseline_v39.md`
  - `docs/secret_rotation_leakage_response_pack_v39.md`
  - `docs/release_gate_rollback_governance_pack_v39.md`
  - `docs/security_regression_compliance_evidence_pack_v39.md`
  - `docs/production_readiness_checklist.md`
  - `docs/enterprise_production_landing_roadmap.md`
- 脚本：
  - `scripts/compliance_security_baseline.py`
  - `scripts/secret_rotation_leakage_response_pack.py`
  - `scripts/release_gate_rollback_governance_pack.py`
  - `scripts/security_regression_compliance_evidence_pack.py`
- 测试：
  - `tests/test_compliance_security_baseline_v391.py`
  - `tests/test_secret_rotation_leakage_response_pack_v392.py`
  - `tests/test_release_gate_rollback_governance_pack_v393.py`
  - `tests/test_security_regression_compliance_evidence_pack_v394.py`
- 版本同步：
  - `pyproject.toml`
  - `app/main.py`
  - `app/tools/mcp/stdio_client.py`
  - 相关版本断言测试

## Verification Matrix

| 验证项 | 命令 | 结果 |
|---|---|---|
| Phase 19.1 | `python -m pytest tests/test_compliance_security_baseline_v391.py -q` | passed |
| Phase 19.2 | `python -m pytest tests/test_secret_rotation_leakage_response_pack_v392.py -q` | passed |
| Phase 19.3 | `python -m pytest tests/test_release_gate_rollback_governance_pack_v393.py -q` | passed |
| Phase 19.4 | `python -m pytest tests/test_security_regression_compliance_evidence_pack_v394.py -q` | passed |
| v3.9 聚焦验证 | `python -m pytest tests/test_runtime_hardening_v055.py tests/test_operations_summary_v312.py tests/test_mcp_stdio_client_v31.py tests/test_compliance_security_baseline_v391.py tests/test_secret_rotation_leakage_response_pack_v392.py tests/test_release_gate_rollback_governance_pack_v393.py tests/test_security_regression_compliance_evidence_pack_v394.py -q` | 56 passed, 2 warnings |
| v3.9 关联回归 | `python -m pytest tests/test_compliance_security_baseline_v391.py tests/test_secret_rotation_leakage_response_pack_v392.py tests/test_release_gate_rollback_governance_pack_v393.py tests/test_security_regression_compliance_evidence_pack_v394.py tests/test_security_v04.py tests/test_guardrails_v44.py tests/test_guardrails_pii_leak_v44.py tests/test_security_headers_v71.py tests/test_request_guards_v72.py tests/test_auth_v20.py tests/test_rbac_v20.py tests/test_cross_tenant_audit_evidence_v365.py tests/test_audit_v045.py tests/test_audit_retention_export_v74.py tests/test_deployment_guard_v60.py -q` | 161 passed, 2 warnings |
| 全量回归 | `python -m pytest -q` | 920 passed, 4 skipped, 2 warnings |
| Diff 检查 | `git diff --check` | passed，仅 CRLF 提示 |

## Security And Privacy

- 所有新增脚本只输出 env name 与 present 布尔状态，不读取或输出真实 secret 原文。
- 默认不连接真实外部系统，不调用真实 LLM，不执行真实 MCP。
- 默认不执行真实安全扫描、密钥轮换、权限变更、审计导出、发布或回滚。
- `skipped` 语义保留，缺少 opt-in、正式签核或演练证据不得伪造成 `success`。

## Operational Boundary

- 当前交付是合规安全治理前的只读证据基线，不是企业级合规、安全治理、密钥治理、发布门禁或回滚验收完成。
- 当前仍不宣称公网生产可直接上线。
- 当前仍不宣称真实 LLM 生产验收、生产级 SSO/OIDC、多租户、复杂 BI、企业级 SRE/DR/容量验收完成。
- 本轮 release prep 不打 tag、不创建 GitHub Release、不移动历史 tag。

## Go/No-Go

- Go：可以进入 `v3.9.0` tag 前最终复核，并继续准备外部安全扫描、正式签核、密钥轮换、发布门禁和回滚演练证据。
- No-Go：不得把本轮只读 runbook 与 `skipped/partial` 结果当作企业级安全合规或生产发布批准。

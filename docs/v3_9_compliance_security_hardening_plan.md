# v3.9 Compliance Security Hardening 规划

## 定位

- v3.9 = **Compliance Security Hardening**。
- 核心目标：面向企业合规、安全治理和发布门禁，补齐上线前的审计、权限、密钥、数据、变更、回滚和安全测试证据。
- 当前已进入 v3.9.0 release prep，版本已同步为 `3.9.0`。
- 本轮不打 tag，不创建 GitHub Release，不移动历史 tag。

## 边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 默认不连接真实 IdP、APM、日志平台、告警平台、对象存储、PostgreSQL、Redis、外部 MCP 或业务系统。
- 默认不执行真实安全扫描、真实密钥轮换、真实权限变更、真实审计导出、真实发布、真实回滚或真实外部系统调用。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码、告警 webhook 或生产 URL 原文。
- 不把配置模板、只读脚本或 runbook 宣称为企业级合规、安全治理或发布门禁验收完成。

## Phase 19.1：Compliance security baseline inventory（P0）

### 目标

建立合规安全基线盘点，明确当前 deployment guard、安全响应头、request guard、结构化日志脱敏、审计留存与导出、RBAC、OIDC、prompt injection、PII guard、跨租户审计和 release review 证据缺口。

### 交付物

- runbook：`docs/compliance_security_baseline_v39.md`
- 只读脚本：`scripts/compliance_security_baseline.py`
- 测试：`tests/test_compliance_security_baseline_v391.py`
- 默认输出目录：`docs/reports/compliance_security_baseline/`

### 不做什么

- 不执行真实安全扫描。
- 不读取 `.env` 或真实 secret 值。
- 不执行真实审计导出。
- 不修改权限、角色、用户或租户数据。
- 不触发真实发布、回滚或外部系统调用。

## Phase 19.2：Secret rotation and leakage response pack（P1）

建立密钥创建、存储、轮换、撤销、泄漏响应和审计流程证据包。默认只读，不执行真实密钥轮换。

### 执行状态（已完成）

- 已新增 runbook：`docs/secret_rotation_leakage_response_pack_v39.md`。
- 已新增只读脚本：`scripts/secret_rotation_leakage_response_pack.py`。
- 已新增测试：`tests/test_secret_rotation_leakage_response_pack_v392.py`。
- 默认输出目录：`docs/reports/secret_rotation_leakage_response/`。
- 默认执行结果在缺少轮换、泄漏响应或撤销恢复演练证据时为 `skipped`，并保留缺失条件列表。
- 验证通过：
  - `python -m pytest tests/test_secret_rotation_leakage_response_pack_v392.py -q`
  - `python scripts/secret_rotation_leakage_response_pack.py --output-dir <temp>`
- 本阶段未读取 `.env` 或真实 secret 值，未连接真实密钥系统，未执行真实密钥创建、轮换、撤销、禁用、泄漏扫描或告警通知。

## Phase 19.3：Release gate and rollback governance pack（P1）

建立发布门禁、变更审批、迁移预检、回滚策略、冻结窗口和变更记录证据包。默认只读，不执行真实发布或回滚。

### 执行状态（已完成）

- 已新增 runbook：`docs/release_gate_rollback_governance_pack_v39.md`。
- 已新增只读脚本：`scripts/release_gate_rollback_governance_pack.py`。
- 已新增测试：`tests/test_release_gate_rollback_governance_pack_v393.py`。
- 默认输出目录：`docs/reports/release_gate_rollback_governance/`。
- 默认执行结果在缺少变更审批、发布签核或回滚演练证据时为 `skipped`，并保留缺失条件列表。
- 验证通过：
  - `python -m pytest tests/test_release_gate_rollback_governance_pack_v393.py -q`
  - `python scripts/release_gate_rollback_governance_pack.py --output-dir <temp>`
- 本阶段未执行 git tag、GitHub Release、部署、迁移、回滚、数据恢复或外部系统调用。

## Phase 19.4：Security regression and compliance evidence pack（P1）

建立安全回归与合规证据包，覆盖 prompt injection、PII 泄漏、越权访问、跨租户访问、审计绕过、限流绕过和导出脱敏。

### 执行状态（已完成）

- 已新增 runbook：`docs/security_regression_compliance_evidence_pack_v39.md`。
- 已新增只读脚本：`scripts/security_regression_compliance_evidence_pack.py`。
- 已新增测试：`tests/test_security_regression_compliance_evidence_pack_v394.py`。
- 默认输出目录：`docs/reports/security_regression_compliance_evidence/`。
- 默认执行结果在缺少外部安全扫描、正式安全签核或合规证据复核时为 `skipped`，并保留缺失条件列表。
- 验证通过：
  - `python -m pytest tests/test_security_regression_compliance_evidence_pack_v394.py -q`
  - `python scripts/security_regression_compliance_evidence_pack.py --output-dir <temp>`
- 本阶段未执行真实 SAST、DAST、依赖扫描、红队测试、外部审计或外部系统调用。

## Phase 19.5：v3.9 release prep（P2）

完成 v3.9 release prep，同步版本号、release notes、release review 和 tag 决策前复核材料。本轮 release prep 不自动打 tag、不创建 GitHub Release。

### 执行状态（已完成）

- 版本已同步到 `3.9.0`。
- 已新增 release notes：`RELEASE_NOTES_v3.9.0.md`。
- 已新增 release review：`docs/release_review_v3.9_compliance_security_hardening.md`。
- Phase 19.1~19.4 纳入 v3.9.0 release prep 范围。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 保持默认 fake/offline，不连接真实外部系统，不执行真实安全扫描、红队测试、审计导出、密钥轮换、权限变更、发布、回滚或迁移。
- 不宣称公网生产可直接上线，不宣称企业级合规、安全治理、密钥治理、发布门禁、回滚验收、真实 LLM 生产验收、生产级 SSO/OIDC 或多租户完成。

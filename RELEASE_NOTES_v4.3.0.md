# Project B v4.3.0 - Operational Governance Console Readiness

## 定位

v4.3.0 聚焦 Operational Governance Console Readiness，将 v4.0~v4.2 的生产上线评审、上线阻断项、关闭证据、人工签核、受控生产验收和验收缺口，纳入 `/operations` 只读运营治理视图。该版本仍保持默认 fake/offline，不触发真实外部系统，不读取报告正文，不执行清理、审批、关闭 blocker/gap、tag 或 GitHub Release 动作。

## 交付范围

- v4.0：Production Launch Readiness
  - `docs/v4_0_production_launch_readiness_plan.md`
  - `docs/production_launch_readiness_review_v40.md`
  - `scripts/production_launch_readiness_review.py`
  - `docs/launch_blocker_register_v40.md`
  - `scripts/launch_blocker_register.py`
  - `docs/production_runbook_finalization_v40.md`
  - `scripts/production_runbook_finalization.py`
- v4.1：Evidence Execution & Closure Pack
  - `docs/v4_1_evidence_execution_closure_plan.md`
  - `docs/launch_blocker_closure_workflow_v41.md`
  - `scripts/launch_blocker_closure_workflow.py`
  - `docs/closure_evidence_index_v41.md`
  - `scripts/closure_evidence_index.py`
  - `docs/manual_signoff_package_v41.md`
  - `scripts/manual_signoff_package.py`
- v4.2：Controlled Production Acceptance Drills
  - `docs/v4_2_controlled_production_acceptance_plan.md`
  - `docs/controlled_production_acceptance_drill_v42.md`
  - `scripts/controlled_production_acceptance_drill.py`
  - `docs/acceptance_drill_evidence_index_v42.md`
  - `scripts/acceptance_drill_evidence_index.py`
  - `docs/production_acceptance_gap_register_v42.md`
  - `scripts/production_acceptance_gap_register.py`
- v4.3：Operational Governance Console Readiness
  - `docs/v4_3_operational_governance_console_readiness_plan.md`
  - `/operations/summary` 的 `observability.v4_evidence`
  - 前端 `/operations` v4 evidence 只读展示
  - v4 evidence 空态与状态语义展示
- v4.3.0 release prep
  - 版本同步到 `4.3.0`
  - `docs/release_review_v4.3_operational_governance_console_readiness.md`

## 运营边界

- 默认不执行真实 LLM、真实外部 MCP、真实 IdP、真实业务系统、真实 PostgreSQL、真实 Redis、真实 APM、真实日志平台、真实告警平台、KMS/Vault 或云平台连接。
- 默认不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、审计导出、密钥轮换或权限变更。
- `/operations` 只展示结构化元数据、路径、计数和边界提示，不读取 Markdown 报告正文，不展开报告内容。
- `metadata_available` 仅表示目录中存在 JSON 元数据，不代表验收通过。
- `partial` 和 `success` 均不等于生产上线批准；公网生产直上仍为 No-Go。
- 本轮 release prep 不打 `v4.3.0` tag，不创建 GitHub Release，不移动历史 tag。

## 未完成项

- 真实外部 LLM/MCP/IdP/PostgreSQL/Redis/业务系统生产验收仍未完成。
- 生产级 SSO/OIDC、多租户、复杂 BI、企业级 SRE/DR/容量验收仍未宣称完成。
- 正式生产上线批准、CAB 签核、变更审批、回滚演练和外部安全合规签核仍需独立执行。
- 公网生产直上仍为 No-Go。

## 验证建议

```powershell
D:\codex安装\tools\Python312\Scripts\pytest.exe tests/test_runtime_hardening_v055.py tests/test_operations_summary_v312.py tests/test_mcp_stdio_client_v31.py tests/test_production_launch_readiness_review_v401.py tests/test_launch_blocker_register_v402.py tests/test_production_runbook_finalization_v403.py tests/test_launch_blocker_closure_workflow_v411.py tests/test_closure_evidence_index_v412.py tests/test_manual_signoff_package_v413.py tests/test_controlled_production_acceptance_drill_v421.py tests/test_acceptance_drill_evidence_index_v422.py tests/test_production_acceptance_gap_register_v423.py
cd frontend
npm run lint
npm run build
git diff --check
```

本轮 release prep 仅形成 tag 前本地复核材料，不创建 tag 或 GitHub Release。

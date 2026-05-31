# v3.4 Phase 14.5 企业内网试点交接清单

## 目标

Phase 14.5 面向企业内网试点交接，整理角色、权限、恢复步骤、验收证据、已知限制与下一步决策。

## 角色与权限边界

| 角色 | 主要职责 | 边界 |
|------|----------|------|
| admin | 配置预检、演练窗口确认、审批策略复核 | 默认 RBAC 关闭；企业试点需显式启用 AUTH_ENABLED 与 RBAC_ENABLED |
| operator | 日常 `/operations` 查看、故障演练、证据归档 | 只读优先，不绕过后端 ToolGateway / PolicyEngine / 审批链路 |
| viewer | 查看只读摘要、报告和 handoff 证据 | 不执行写入型工具动作 |
| auditor | 审计导出、脱敏边界、release/tag 记录复核 | 审计导出默认脱敏 |

## 交接证据

- 操作员工作流：`docs/operator_workflow_polish_v34.md`
- 故障演练包：`docs/incident_rehearsal_pack_v34.md`
- 证据归档 manifest：`docs/evidence_archive_manifest_v34.md`
- 可选集成准备度矩阵：`docs/optional_integration_readiness_matrix_v34.md`
- 备份恢复清单：`docs/backup_restore_checklist_v31.md`
- 运维排障索引：`docs/operations_troubleshooting_index_v31.md`

## OIDC 与真实 LLM 解释

- OIDC 当前是最小 IdP 配置演练边界，不等于生产级 SSO/OIDC 完成。
- 真实 LLM opt-in 缺少条件时必须 `skipped`。
- 真实 LLM smoke 仅为 opt-in 验收，不等于生产验收完成。
- 默认 pytest/CI 不调用真实 LLM。

## Go / No-Go

- 企业内网试点：Go。
- 公网直上：No-Go。
- 真实生产验收：需另行执行并形成独立证据。

## 已知限制

- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- 真实外部 MCP、生产级 SSO/OIDC、多租户和复杂 BI 仍需后续专项验收。

## 只读生成脚本

```powershell
python scripts/pilot_handoff_checklist.py --output-dir docs/reports/pilot_handoff
```

脚本只生成交接清单 JSON 与 Markdown，不读取 secret 原文，不执行真实外网 LLM，不写业务数据。

## 验证

```powershell
python -m pytest tests/test_pilot_handoff_checklist_v345.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
docker compose config
```

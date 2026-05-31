# v3.4.0 发布复核 - Pilot Hardening & Operator Experience

## 范围

- 完成 v3.4 Phase 14.1~14.5 交付收口。
- 同步版本标记到 `3.4.0`。
- 新增 release notes、release review、验证矩阵与 tag 决策前边界声明。
- 本轮不打 tag，不创建 GitHub Release。

## 变更文档 / 脚本 / 测试 / 模块

- 版本同步：`pyproject.toml`、`app/main.py`、`app/tools/mcp/stdio_client.py`。
- 脚本版本字段：acceptance snapshot、failure diagnostics、live drill window、operator workflow、incident rehearsal、evidence archive、optional integration readiness、pilot handoff。
- 新增文档：
  - `docs/operator_workflow_polish_v34.md`
  - `docs/incident_rehearsal_pack_v34.md`
  - `docs/evidence_archive_manifest_v34.md`
  - `docs/optional_integration_readiness_matrix_v34.md`
  - `docs/pilot_handoff_checklist_v34.md`
  - `RELEASE_NOTES_v3.4.0.md`
- 新增测试：
  - `tests/test_operator_workflow_index_v341.py`
  - `tests/test_incident_rehearsal_pack_v342.py`
  - `tests/test_evidence_archive_manifest_v343.py`
  - `tests/test_optional_integration_readiness_v344.py`
  - `tests/test_pilot_handoff_checklist_v345.py`

## 验证矩阵

| 验证项 | 结果口径 |
|--------|----------|
| Phase 14.1~14.5 目标测试 | 通过 |
| `python -m pytest -q` | 通过 |
| `docker compose config` | 通过 |
| `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` | 按 release prep 验证执行 |
| `npm --prefix frontend run lint` | 通过 |
| `npm --prefix frontend run build` | 通过 |
| UTF-8 与乱码串扫描 | 通过 |
| 误宣称扫描 | 通过 |

## 安全与隐私边界

- 所有新增脚本默认只读。
- 不删除用户数据。
- 不自动清理报告。
- 不修改 `.env`。
- 不读取或输出真实 secret 原文。
- 不执行真实外网 LLM。
- 审计与证据路径保持脱敏边界。

## 运维边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 缺少真实 LLM/OIDC/外部 MCP opt-in 条件时记录为 `skipped`，不得伪造成成功。
- `auth_enabled`、`rbac_enabled`、`redis_enabled` 默认不强制启用。
- `storage_backend` 默认仍保留 sqlite 路径。

## 已知限制

- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- 真实外部 MCP Server、生产级 SSO/OIDC、多租户、复杂 BI 仍需后续专项验收。

## Go / No-Go

- **Go**：可进入 v3.4.0 tag 前最终复核。
- **No-Go**：本轮不打 tag，不创建 GitHub Release。
- **No-Go**：公网直上仍不允许。

# v3.5.0 发布复核 - Controlled Pilot Expansion & Evidence Operations

## 范围

- 完成 v3.5 Phase 15.1~15.5 交付收口。
- 同步版本标记到 `3.5.0`。
- 新增 release notes、release review、验证矩阵与 tag 决策前边界声明。
- 本轮不打 tag，不创建 GitHub Release。

## 变更文档 / 脚本 / 测试 / 模块

- 版本同步：`pyproject.toml`、`app/main.py`、`app/tools/mcp/stdio_client.py`。
- 脚本版本字段：acceptance snapshot、failure diagnostics、live drill window、operator workflow、incident rehearsal、evidence archive、optional integration readiness、pilot handoff、pilot evidence comparison、operator drill scoring、controlled integration dry-run、governance exception register、pilot closeout report pack。
- 新增文档：
  - `docs/pilot_evidence_comparison_v35.md`
  - `docs/operator_drill_scoring_rubric_v35.md`
  - `docs/controlled_integration_dry_run_v35.md`
  - `docs/governance_exception_register_v35.md`
  - `docs/pilot_closeout_report_pack_v35.md`
  - `docs/enterprise_production_landing_roadmap.md`
  - `RELEASE_NOTES_v3.5.0.md`
- 新增测试：
  - `tests/test_pilot_evidence_comparison_v351.py`
  - `tests/test_operator_drill_scoring_v352.py`
  - `tests/test_controlled_integration_dry_run_v353.py`
  - `tests/test_governance_exception_register_v354.py`
  - `tests/test_pilot_closeout_report_pack_v355.py`

## 验证矩阵

| 验证项 | 结果口径 |
|--------|----------|
| Phase 15.1~15.5 目标测试 | 24 passed |
| runtime / health / MCP stdio version 回归 | 36 passed, 1 warning |
| `python -m pytest -q` | 831 passed, 4 skipped, 1 warning |
| `docker compose config` | 通过 |
| `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` | 使用脱敏占位环境变量通过 |
| `npm --prefix frontend run lint` | 通过 |
| `npm --prefix frontend run build` | 通过 |
| UTF-8 与乱码特征扫描 | 通过 |
| secret 明文扫描 | 通过 |

## 安全与隐私边界

- 所有新增脚本默认只读，仅写入指定报告输出目录。
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
- release prep 不自动创建 tag 或 GitHub Release。

## 已知限制

- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- 真实外部 MCP Server、生产级 SSO/OIDC、多租户和复杂 BI 仍需后续专项验收。
- v3.5 的证据运营与收口报告不替代人工安全评审和生产上线评审。

## Go / No-Go

- **Go**：可进入 v3.5.0 tag 前最终复核。
- **No-Go**：本轮不打 tag，不创建 GitHub Release。
- **No-Go**：公网直上仍不允许。
- **Manual decision**：是否创建 `v3.5.0` tag 和 GitHub Release 需用户单独确认。

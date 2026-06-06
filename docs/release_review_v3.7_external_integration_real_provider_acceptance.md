# v3.7.0 发布复核 - External Integration & Real Provider Acceptance

## 范围

- 完成 v3.7 Phase 17.1~17.5 交付收口。
- 同步版本标记到 `3.7.0`。
- 新增 release notes、release review、验证矩阵与 tag 决策前边界声明。
- 本轮不打 tag，不创建 GitHub Release。

## 变更文档 / 脚本 / 测试 / 模块

- 版本同步：`pyproject.toml`、`app/main.py`、`app/tools/mcp/stdio_client.py`。
- 新增文档：
  - `docs/external_provider_acceptance_inventory_v37.md`
  - `docs/external_mcp_acceptance_gate_v37.md`
  - `docs/real_llm_provider_acceptance_gate_v37.md`
  - `docs/store_redis_readiness_drill_v37.md`
  - `docs/business_system_integration_safety_checklist_v37.md`
  - `RELEASE_NOTES_v3.7.0.md`
- 新增脚本：
  - `scripts/external_provider_acceptance_inventory.py`
  - `scripts/external_mcp_acceptance_gate.py`
  - `scripts/real_llm_provider_acceptance_gate.py`
  - `scripts/store_redis_readiness_drill.py`
  - `scripts/business_system_integration_safety_checklist.py`
- 新增测试：
  - `tests/test_external_provider_acceptance_inventory_v371.py`
  - `tests/test_external_mcp_acceptance_gate_v372.py`
  - `tests/test_real_llm_provider_acceptance_gate_v373.py`
  - `tests/test_store_redis_readiness_drill_v374.py`
  - `tests/test_business_system_integration_safety_checklist_v375.py`

## 验证矩阵

| 验证项 | 结果口径 |
|--------|----------|
| Phase 17.1~17.5 新增门禁测试 | 25 passed, 1 warning |
| runtime / health / MCP stdio / operations version 回归 | 36 passed, 2 warnings |
| storage / redis / deployment guard / request guards 回归 | 77 passed, 2 warnings |
| security / audit / approval resume / full resume 回归 | 63 passed, 2 warnings |
| `python -m pytest -q` | 880 passed, 4 skipped, 2 warnings |
| `docker compose config` | 通过，仅 Docker config 读权限 warning |
| `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` | 通过，仅 Docker config 读权限 warning |
| `git diff --check` | 通过，仅 CRLF 转换提示 |

## 安全与隐私边界

- 所有新增脚本默认只读，仅写入指定报告输出目录。
- 不删除用户数据。
- 不自动清理报告。
- 不修改 `.env`。
- 不读取或输出真实 secret 原文。
- 不输出 prompt 原文。
- 不连接真实外部 MCP。
- 不调用真实外网 LLM。
- 不连接真实 PostgreSQL 或 Redis。
- 不连接真实业务系统。
- 不执行真实业务系统读写。
- 不绕过 ToolGateway、PolicyEngine、审批链路或审计链路。

## 运维边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- `MCP_MODE=fake` 默认保持。
- `AUTH_ENABLED`、`RBAC_ENABLED`、`OIDC_ENABLED`、`REDIS_ENABLED` 默认不强制启用。
- `storage_backend` 默认仍保留 sqlite 路径。
- release prep 不自动创建 tag 或 GitHub Release。

## 已知限制

- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收完成。
- 不宣称真实外部 MCP 生产验收完成。
- 不宣称 PostgreSQL、Redis 或多实例限流生产验收完成。
- 不宣称真实业务系统生产集成验收完成。
- 不宣称生产级 SSO/OIDC、多租户或复杂 BI 全量完成。
- 真实 provider、真实业务系统和生产容量仍需后续人工受控验收。

## Go / No-Go

- **Go**：可进入 v3.7.0 tag 前最终复核。
- **No-Go**：本轮不打 tag，不创建 GitHub Release。
- **No-Go**：公网直上仍不允许。
- **Manual decision**：是否创建 `v3.7.0` tag 和 GitHub Release 需用户单独确认。

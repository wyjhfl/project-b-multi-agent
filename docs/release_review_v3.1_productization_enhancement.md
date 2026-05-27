# v3.1.0 Release Review — Productization Enhancement

## 1) Scope

- 目标：完成 v3.1.0 Productization Enhancement 的 release prep 收口。
- 范围：版本号同步、release notes/review 文档、README/AGENTS/运行手册/检查清单口径统一、验证基线更新。
- 非目标：本轮不打 tag、不创建 GitHub Release、不执行真实外网 LLM。

## 2) Changed docs/modules

- 版本号同步：
  - `pyproject.toml`
  - `app/main.py`（FastAPI version 与 `/health.version`）
  - `app/tools/mcp/stdio_client.py`（fallback version）
  - `tests/test_runtime_hardening_v055.py`
  - `tests/test_mcp_stdio_client_v31.py`
- 新增文档：
  - `RELEASE_NOTES_v3.1.0.md`
  - `docs/release_review_v3.1_productization_enhancement.md`
- 口径收口更新：
  - `README.md`
  - `AGENTS.md`
  - `docs/v3_1_productization_enhancement_plan.md`
  - `docs/deployment_runbook.md`
  - `docs/production_readiness_checklist.md`

## 3) Verification matrix

- 测试与配置验证命令（本轮执行）：
  - `python -m pytest tests/test_demo_seed_data_v311.py tests/test_operations_summary_v312.py -q`
  - `python -m pytest tests/test_oidc_config_v75.py tests/test_deployment_guard_v60.py -q`
  - `python -m pytest tests/test_runtime_hardening_v055.py tests/test_mcp_stdio_client_v31.py -q`
  - `python -m pytest -q`
  - `docker compose config`
  - `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`（缺变量应失败）
  - 注入临时 `JWT_SECRET`/`DATABASE_URL`/`REDIS_URL` 后 prod compose config 应通过，并清理变量
  - `frontend npm run lint`
  - `frontend npm run build`
- 预期基线：`754 passed, 4 skipped`（如复跑变化，以实测为准）。

## 4) Security / privacy boundary

- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- 真实 LLM 仅 opt-in；本轮 release prep 未执行真实外网 LLM。
- 不提交 API key/token/client_secret/JWT_SECRET/DATABASE_URL/REDIS_URL 等真实凭据。
- 不默认接入真实外部 MCP。
- 审计导出、pilot reports、operations summary 保持脱敏与只读边界。

## 5) Operational boundary

- v3.1.0 定位为企业内网试点后的产品化增强，不等于公网生产直接上线。
- deployment runbook / troubleshooting / backup restore 为 runbook 级演练材料，不引入复杂运维平台。
- OIDC 仅最小真实 IdP 配置演练与预检，不宣称生产级 SSO/OIDC 完成。

## 6) Known limitations

- 真实 LLM 生产验收未完成（仅 opt-in 受控路径）。
- 真实外部 MCP 生产验收未完成。
- 多租户、复杂 BI、完整生产级 SSO/OIDC 未完成。
- 当前限流仍以单实例友好的进程内方案为主，多实例生产需额外能力补齐。

## 7) Go / No-Go

- **Go**：企业内网试点 / 准生产演示。
- **No-Go**：公网生产直接上线。
- **No-Go**：对外声明“真实 LLM 生产验收完成”或“生产级 SSO/OIDC、多租户、复杂 BI 全量完成”。

## 8) 结论

- 结论：可进入 **v3.1.0 tag 决策**。
- 说明：本轮仅 release prep，不打 tag，不创建 GitHub Release。

# v2.6.0 Release Review：Engineering Readiness

## 1. Scope

本次 review 聚焦 v2.6.0 的 Phase 6.0 工程化收口：部署门禁、生产模板、运维脚本、验证口径与文档一致性。

## 2. Changed modules

- 后端配置与门禁：
  - `app/core/deployment_guard.py`
  - `app/api/deployment.py`
  - `app/main.py`
- MCP 元数据版本对齐：
  - `app/tools/mcp/stdio_client.py`
- 生产模板与脚本：
  - `docker-compose.prod.yml`
  - `.env.production.example`
  - `scripts/prod_config_check.ps1`
- 测试：
  - `tests/test_deployment_guard_v60.py`
  - `tests/test_runtime_hardening_v055.py`
  - `tests/test_mcp_stdio_client_v31.py`
- 文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/deployment_runbook.md`
  - `docs/engineering_rollout_plan_v26.md`
  - `RELEASE_NOTES_v2.6.0.md`

## 3. Verification matrix

- 部署门禁测试：通过。
- 运行时版本与健康检查测试：通过。
- preflight/smoke/judge 默认路径验证：通过（real_llm 用例按预期 skip）。
- 全量回归：`671 passed, 4 skipped`。
- compose 默认配置：通过。
- compose prod override：缺敏感变量失败、注入临时安全变量后通过。
- 前端 lint/build：通过。
- prod_config_check 脚本：development warning 通过、production 合法配置通过。

## 4. Security / privacy boundary

- 不提交 API key、token、账号凭据。
- 部署检查错误信息不回显密钥、token、连接串密码。
- 默认 fake/offline，不引入真实外部 MCP 作为默认依赖。
- 默认 pytest 不调用真实 LLM。

## 5. Deployment readiness boundary

- 结论定位：企业内网试点准生产可投入使用。
- 明确不等于公网生产可直接上线。
- 真实 LLM 仅 opt-in 验收，不进入默认路径。

## 6. Known limitations

- 不包含生产级 SSO/OIDC。
- 不包含多租户。
- 不包含复杂 BI。
- 不包含真实外部 MCP Server 生产验收完成。
- 不宣称真实 LLM 生产验收完成。

## 7. Go / No-Go

- 结论：**Go（建议进入 v2.6.0 tag 决策）**。
- 说明：本轮仅 release prep，不打 tag，不创建 GitHub Release。

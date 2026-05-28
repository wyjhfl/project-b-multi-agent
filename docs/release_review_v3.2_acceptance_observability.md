# v3.2.0 Release Review：Acceptance & Observability Enhancement

## 1. Scope

- 版本范围：v3.2.0 release prep（不打 tag、不创建 Release）。
- 目标：收口 Phase 12.1~12.5，形成 v3.2.0 tag 决策材料。

## 2. Changed docs/modules

- 版本同步：`pyproject.toml`、`app/main.py`、`app/tools/mcp/stdio_client.py`
- 测试同步：`tests/test_runtime_hardening_v055.py`、`tests/test_mcp_stdio_client_v31.py`、`tests/test_operations_summary_v312.py`、`tests/test_acceptance_snapshot_v321.py`
- 观测与验收脚本：`scripts/acceptance_snapshot.py`、`scripts/demo_artifact_bundle.py`、`scripts/failure_diagnostics.py`
- 关键文档：`RELEASE_NOTES_v3.2.0.md`、`docs/failure_diagnostics_pack_v32.md`、`docs/real_llm_optional_retry_log_v32.md`

## 3. Verification matrix

- 后端/脚本相关定向测试：acceptance snapshot、demo artifact、failure diagnostics、operations summary、runtime/mcp 版本断言
- 全量回归：`python -m pytest -q`
- 配置校验：`docker compose config`、prod compose 缺变量失败 + 临时变量注入后通过
- 前端校验：`frontend npm run lint`、`frontend npm run build`

## 4. Security/privacy boundary

- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- Phase 12.5 本轮为 skipped，未执行真实外网 LLM。
- 报告/快照/artifact/diagnostics 持续执行脱敏边界：
  - 不输出 prompt/query/raw_prompt/sql_prompt 原文
  - 不输出 key/token/client_secret/password/JWT_SECRET/DATABASE_URL/REDIS_URL 明文
  - DSN 密码保持脱敏

## 5. Operational boundary

- v3.2.0 面向企业内网试点/准生产演示验收，不等于公网生产直接上线。
- 只读运维观测与故障诊断能力增强，不引入复杂运维平台。
- 不移动 `v3.1.0` / `v3.0.0` tag，不改历史发布事实。

## 6. Known limitations

- 真实 LLM 证据重试依赖用户手动提供完整 opt-in 环境变量；本轮未满足，故 skipped。
- OIDC 仍为最小接入骨架与配置预检，不是生产级 SSO/OIDC 完成声明。
- 多租户、复杂 BI 仍不在本轮交付范围。

## 7. Go/No-Go

- **Go**：进入 v3.2.0 annotated tag 决策（企业内网试点/准生产演示语境）。
- **No-Go**：公网生产直接上线声明、真实 LLM 生产验收完成声明、生产级 SSO/OIDC/多租户/复杂 BI 全量完成声明。

## 8. 结论

- 当前代码与文档已满足 v3.2.0 release prep 收口要求。
- 可以进入 v3.2.0 tag 决策；**本轮不打 tag**。

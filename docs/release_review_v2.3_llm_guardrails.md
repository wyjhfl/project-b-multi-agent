# v2.3.0 Release Review：LLM Provider + Guardrails Runtime

## 1. Scope

本次仅执行 v2.3.0 release prep，不新增功能，不创建 tag，不创建 GitHub Release。

覆盖范围：

- 版本号同步（`pyproject.toml`、`app/main.py`、`/health`、测试断言）
- 文档口径统一（README/AGENTS/Phase 4 计划文档）
- 新增 release notes 与 release review 文档
- 回归测试与 Docker 校验

## 2. Changed modules

- 版本与运行信息：
  - `pyproject.toml`
  - `app/main.py`
  - `tests/test_runtime_hardening_v055.py`
- 说明文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/llm_provider_guardrails_plan_v4.md`
  - `RELEASE_NOTES_v2.3.0.md`
  - `docs/release_review_v2.3_llm_guardrails.md`

## 3. Verification

建议验收命令：

- `python -m pytest tests/test_runtime_hardening_v055.py -q`
- `python -m pytest tests/test_llm_budget_cache_v45.py tests/test_guardrails_pii_leak_v44.py tests/test_llm_judge_v43.py -q`
- `python -m pytest -q`
- `docker compose config`
- `docker compose build app`

预期结果口径：

- 全量测试：**636 passed**
- Docker compose config：通过
- Docker build app：通过

## 4. Security / Privacy notes

- Guardrails 已完成规则编排与 PII 脱敏链路，findings 对外仅暴露脱敏值。
- 默认 fake/offline，不在默认测试中调用真实 LLM。
- 高风险能力仍通过既有策略链路控制，不绕过审批与审计。

## 5. Known limitations

- 真实外部 MCP Server 生产验收未在本次 release prep 范围内完成。
- 真实 LLM 生产验收依赖外部环境与密钥，需独立验收。
- PII 防护为规则型检测，不等同完整 DLP。
- 成本治理为运行期轻量预算与聚合观测，不是完整成本账单系统。
- 完整 LangGraph native Command resume 仍未实现。

## 6. Go / No-Go conclusion

- 在测试与 Docker 校验均通过前提下，建议 **Go（可进入 v2.3.0 tag 决策）**。
- 本文档阶段不执行打 tag；待人工确认后执行 tag 与发布动作。

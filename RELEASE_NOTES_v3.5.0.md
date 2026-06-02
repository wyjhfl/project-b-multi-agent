# v3.5.0 发布说明

## 摘要

v3.5.0 = **Controlled Pilot Expansion & Evidence Operations**。

本轮 release prep 汇总 Phase 15.1~15.5 的受控试点扩展与证据运营能力：证据对比、操作员演练评分、受控集成 dry-run、治理例外登记和试点收口报告包。

## 阶段覆盖

### Phase 15.1 - 试点证据对比快照

- 新增 `docs/pilot_evidence_comparison_v35.md`。
- 新增 `scripts/pilot_evidence_comparison.py` 与 `tests/test_pilot_evidence_comparison_v351.py`。
- 支持 baseline/current manifest JSON 或证据目录输入，仅读取文件元数据，不读取报告正文。
- 缺失或空输入必须 `skipped` 并记录 `warnings`，不得伪造成成功。

### Phase 15.2 - 操作员演练评分 Rubric

- 新增 `docs/operator_drill_scoring_rubric_v35.md`。
- 新增 `scripts/operator_drill_scoring.py` 与 `tests/test_operator_drill_scoring_v352.py`。
- 评分维度覆盖 availability、recoverability、evidence_integrity、configuration_readiness、permission_boundary、known_limitations。
- 不自动改变 Go/No-Go 结论，不读取报告正文，不执行真实外网 LLM。

### Phase 15.3 - 受控集成 dry-run checklist

- 新增 `docs/controlled_integration_dry_run_v35.md`。
- 新增 `scripts/controlled_integration_dry_run.py` 与 `tests/test_controlled_integration_dry_run_v353.py`。
- 覆盖 real LLM、OIDC、external MCP、Postgres、Redis、frontend build/network、deployment guard、audit export redaction。
- 缺少 opt-in 条件必须 `skipped`；发现疑似 secret、非只读来源或真实外部执行风险时标记 `blocked`。

### Phase 15.4 - 治理例外登记

- 新增 `docs/governance_exception_register_v35.md`。
- 新增 `scripts/governance_exception_register.py` 与 `tests/test_governance_exception_register_v354.py`。
- 支持引用 config drift、governance policy summary、incident rehearsal、operator scoring、controlled integration 的 JSON 元数据。
- 不自动批准例外，不绕过 deployment guard、安全响应头、审计脱敏或审批链路。

### Phase 15.5 - 试点收口报告包

- 新增 `docs/pilot_closeout_report_pack_v35.md`。
- 新增 `scripts/pilot_closeout_report_pack.py` 与 `tests/test_pilot_closeout_report_pack_v355.py`。
- 汇总 pilot handoff、evidence archive、optional integration readiness、operator scoring、controlled integration dry-run、governance exception register 的 JSON 元数据。
- 报告包包含 executive summary、evidence summary、known limitations、Go/No-Go、next actions 和 boundary declarations。

## 版本同步

- `pyproject.toml` 已同步到 `3.5.0`。
- FastAPI `app.version` 与 `/health.version` 已同步到 `3.5.0`。
- MCP stdio fallback client version 已同步到 `3.5.0`。
- 脚本 version markers 与相关测试断言已同步到 `3.5.0`。

## 边界声明

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 不执行真实外网 LLM。
- 不提交或输出真实密钥、Token、API Key、client_secret、JWT_SECRET、DATABASE_URL、REDIS_URL。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户或复杂 BI 全量完成。
- 本轮 release prep 不打 tag，不创建 GitHub Release，不移动历史 tag。

## 验证

- `python -m pytest tests/test_pilot_evidence_comparison_v351.py tests/test_operator_drill_scoring_v352.py tests/test_controlled_integration_dry_run_v353.py tests/test_governance_exception_register_v354.py tests/test_pilot_closeout_report_pack_v355.py -q`
- `python -m pytest tests/test_runtime_hardening_v055.py tests/test_mcp_stdio_client_v31.py tests/test_operations_summary_v312.py -q`
- `python -m pytest -q`：831 passed, 4 skipped, 1 warning。
- `docker compose config`
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`
- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`

最终 tag 与 GitHub Release 创建需用户单独确认。

# v3.7 Phase 17.3 Real LLM provider acceptance gate

## 目标

Phase 17.3 建立真实 LLM provider 验收门禁，覆盖 preflight、smoke、budget、cache、fallback、PII 脱敏、prompt injection guard、输出校验和报告脱敏。

本阶段只读，不调用真实外网 LLM，不执行 provider network check，不读取或输出真实 API key 原文。

## 入口

```powershell
python scripts/real_llm_provider_acceptance_gate.py
```

可指定输出目录和 pilot report 目录：

```powershell
python scripts/real_llm_provider_acceptance_gate.py `
  --pilot-report-dir docs/reports/real_llm_pilot `
  --output-dir docs/reports/real_llm_provider_acceptance_gate/
```

默认输出：

- JSON：`docs/reports/real_llm_provider_acceptance_gate/*_real_llm_provider_acceptance_gate.json`
- Markdown：`docs/reports/real_llm_provider_acceptance_gate/*_real_llm_provider_acceptance_gate.md`

## 门禁项

- `preflight_config`：`REAL_LLM_ACCEPTANCE_ENABLED`、`REAL_LLM_PREFLIGHT_ENABLED`、provider、model、API key env name。
- `network_check_gate`：真实网络检查必须显式 `REAL_LLM_PREFLIGHT_NETWORK_CHECK=true`，默认不执行。
- `smoke_opt_in`：NL2SQL/Judge smoke 必须显式 opt-in。
- `budget_cache_fallback`：预算、缓存、fallback 行为必须有测试覆盖。
- `pii_prompt_guardrails`：PII 脱敏、prompt injection guard 和输出校验必须有测试覆盖。
- `report_redaction`：pilot report JSON/Markdown 必须脱敏，不输出 prompt/secret 原文。
- `judge_acceptance`：LLMJudge opt-in smoke 与 fallback/unavailable 语义必须有测试覆盖。
- `evidence_index`：可选索引 pilot report 目录文件元数据，不读取报告正文。

## 状态语义

- `skipped`：缺少真实 LLM opt-in 条件或必需配置。
- `partial`：本地门禁与测试覆盖存在，但本阶段未执行真实外网 LLM。
- `blocked`：发现真实 API key、prompt 原文、连接串密码等泄漏风险，或只读边界被破坏。
- `success`：保留给后续真实 opt-in smoke 执行完成并形成脱敏证据后使用。

## 只读边界

- 不调用真实外网 LLM。
- 不执行 provider network check。
- 不读取或输出真实 API key、token、client_secret、连接串密码原文。
- 不读取 pilot report 正文，只记录文件元数据。
- 不把 opt-in smoke、fallback 或只读门禁宣称为生产验收完成。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。

## 验证

```powershell
python -m pytest tests/test_real_llm_provider_acceptance_gate_v373.py -q
python -m pytest tests/test_llm_preflight_v51.py tests/test_real_llm_smoke_v52.py tests/test_real_llm_judge_smoke_v54.py tests/test_llm_budget_cache_v45.py tests/test_guardrails_pii_leak_v44.py -q
docker compose config
```

## 后续衔接

- Phase 17.4：Store and Redis production readiness drill。
- 后续真实 LLM opt-in 演练必须单独提供脱敏报告、request_id、tokens、cost、fallback、budget、cache 和审计证据。

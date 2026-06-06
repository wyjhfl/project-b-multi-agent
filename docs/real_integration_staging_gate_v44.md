# v4.4 组合真实集成 staging gate（只读）

## 目标

本脚本用于汇总 v4.4 组合真实集成进入 staging 前的只读证据门禁，输出 JSON 和 Markdown 报告，默认输出目录为 `docs/reports/real_integration_staging_gate/`。

脚本不会连接真实 LLM、PostgreSQL、Redis 或真实 MCP Server，不执行 Alembic migration，不写业务/审计/指标数据，也不会输出 secret 原文。

## 证据来源

脚本只消费以下目录中的 JSON 证据，并只读取结构字段：

- `docs/reports/real_integration_readiness/`
- `docs/reports/real_integration_env_profile/`
- `docs/reports/real_integration_smoke_plan/`
- `docs/reports/real_integration_staging_smoke/`
- `docs/reports/real_llm_provider_acceptance_gate/`
- `docs/reports/external_mcp_acceptance_gate/`
- `docs/reports/store_redis_readiness_drill/`

如果目录不存在、不是目录、或没有 JSON 证据，则对应项必须标记为 `skipped`，不得伪造成 `success`。

## 状态规则

- `partial`：证据目录存在，存在最新 JSON 证据，且源证据状态为 `partial` 或 `success`，同时未发现 secret-like 内容，也未发现异常执行 flag。
- `skipped`：证据目录缺失、无 JSON 证据，或上游证据状态为 `skipped` / `failed`。
- `blocked`：证据 JSON 非法、发现 secret-like 内容、发现异常执行 flag、或上游证据已是 `blocked`。

组合结论规则：

- 七类必需证据全部为脱敏且无 `skipped` / `blocked` 时，组合 gate 状态为 `partial`，`combined_staging_gate=Manual-Review`。
- 只要存在 `skipped`，组合 gate 为 `skipped`，`combined_staging_gate=Needs-Input`。
- 只要存在 `blocked`，组合 gate 为 `blocked`，`combined_staging_gate=Needs-Input`。
- `public_production_direct_launch` 永远是 `No-Go`。

## 强制 false 标志

组合报告固定输出以下字段为 `false`：

- `real_llm_executed`
- `database_connected`
- `redis_connected`
- `external_mcp_connected`
- `migration_executed`
- `business_data_written`
- `audit_data_written`
- `metrics_data_written`
- `secret_plaintext_output`

如果上游 JSON 证据出现这些字段中的任意一个为 `true`，组合 gate 必须标记为 `blocked`。

## Secret 检查

脚本会对读取到的 JSON 字符串叶子值执行 secret-like 模式检查，例如：

- API Key / token / client_secret / password / secret
- `postgres://` / `postgresql://` / `redis://`
- `Bearer ...`
- `sk-...`

一旦发现命中，脚本只记录 `secret_like_content_detected` 这类原因，不输出原文。

## 运行方式

```bash
python scripts/real_integration_staging_gate.py
```

指定输出目录：

```bash
python scripts/real_integration_staging_gate.py --output-dir docs/reports/real_integration_staging_gate
```

指定证据根目录：

```bash
python scripts/real_integration_staging_gate.py --evidence-root docs/reports
```

## 输出内容

JSON 与 Markdown 报告至少包含：

- 生成时间、commit、版本、phase、status
- 七类证据索引结果
- 缺失条件、阻断原因、warning
- 固定 false 的只读边界标志
- `combined_staging_gate` 与 `public_production_direct_launch` 的 Go/No-Go 结论

## 测试

对应测试文件：

- `tests/test_real_integration_staging_gate_v442.py`

测试覆盖：

- 生成 JSON/Markdown
- 缺证据时 `skipped`
- 七类脱敏证据齐全时进入 `partial` / `Manual-Review`
- secret-like 证据触发 `blocked` 且不泄露原文
- 异常执行 flag 触发 `blocked`

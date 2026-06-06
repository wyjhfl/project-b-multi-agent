# v4.4 受控真实集成 Smoke Plan/Gate

## 目标

- 为 `real_llm`、`postgres`、`redis`、`external_mcp` 四个域提供统一的只读 smoke plan/gate 入口。
- 默认输出到 `docs/reports/real_integration_smoke_plan/`，同时生成 JSON 与 Markdown。
- 该入口只做计划与门禁，不执行任何真实连接或真实 smoke。

## 交付物

- 脚本：`scripts/real_integration_smoke_plan.py`
- 测试：`tests/test_real_integration_smoke_plan_v443.py`
- 默认输出目录：`docs/reports/real_integration_smoke_plan/`

## 输出约束

每个域必须输出以下结构化字段：

- `opt_in_conditions`
- `env_present`
- `target_secret_env_present`
- `planned_smoke_steps`
- `blocked_by`
- `missing_conditions`
- `execution_flags`

其中：

- `target_secret_env_present` 仅对 `REAL_LLM_API_KEY_ENV` 指向的 env 做存在性判断，不输出 secret 值。
- `execution_flags` 中的执行标志全部保持 `false`。
- 默认无 opt-in 条件时，域状态与整体状态为 `skipped`。
- 若四个域的 opt-in 条件都齐备，但脚本没有任何执行参数，则整体状态为 `partial`，且 `go_no_go.combined_staging_gate=Manual-Review`。
- 若发现 secret-like 文本，则结果必须 `blocked`，且不得输出原文。

## 边界

- 不连接真实 LLM、PostgreSQL、Redis、外部 MCP。
- 不执行 Alembic migration。
- 不写业务、审计或指标数据。
- 不输出 `DATABASE_URL`、`REDIS_URL`、API Key、Token 等 secret 原文。
- 不提供执行真实连接的 CLI 参数；当前阶段仅做计划门禁。

## CLI

```bash
python -m scripts.real_integration_smoke_plan
python -m scripts.real_integration_smoke_plan --output-dir docs/reports/real_integration_smoke_plan
```

## 状态语义

- `skipped`：缺少一个或多个 opt-in 条件，仅输出缺口与计划步骤。
- `partial`：四个域的 opt-in 条件都已具备，但仍停留在人工复核入口。
- `blocked`：发现 secret-like 文本或其它必须阻断的问题。

## Go/No-Go

- `combined_staging_gate=Manual-Review` 仅表示进入人工复核。
- `public_production_direct_launch` 始终为 `No-Go`。
- 该入口不能替代真实受控 runbook，也不能宣称真实生产验收完成。

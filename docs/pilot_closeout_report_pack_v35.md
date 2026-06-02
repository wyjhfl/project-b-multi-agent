# v3.5 Pilot closeout report pack（只读）

## 定位

Phase 15.5 用于生成试点收口报告包，把既有交接、证据归档、可选集成准备度、操作员评分、受控集成 dry-run 和治理例外登记的 JSON 元数据汇总为管理层与实施团队可复核的收口材料。

本阶段不改业务逻辑，不改版本号，不打 tag，不创建 GitHub Release，不执行真实外网 LLM。当前版本继续保持 `3.4.0`。

## 默认输出

- 脚本：`scripts/pilot_closeout_report_pack.py`
- 测试：`tests/test_pilot_closeout_report_pack_v355.py`
- 默认输出目录：`docs/reports/pilot_closeout/`
- 输出格式：JSON + Markdown

## 输入来源

脚本仅读取 JSON 元数据和结构化摘要字段，不读取报告正文，不读取或输出真实 secret 原文。可选输入包括：

- `--pilot-handoff`：pilot handoff checklist JSON
- `--evidence-archive`：evidence archive manifest JSON
- `--integration-readiness`：optional integration readiness JSON
- `--operator-scoring`：operator drill scoring JSON
- `--controlled-integration`：controlled integration dry-run JSON
- `--governance-exceptions`：governance exception register JSON

缺少输入、路径不存在、JSON 为空或来源状态为 `skipped` 时必须保留 `skipped` 语义，并写入 `missing_conditions`，不得伪造成 `success`。

## 报告结构

报告包包含：

- `executive_summary`：汇总加载来源数量、收口状态、skipped/blocked 来源。
- `evidence_summary`：按来源列出只读元数据摘要、状态、缺失条件计数和告警计数。
- `known_limitations`：保留既有交接限制，并固定声明公网直上、真实 LLM 生产验收、生产级 SSO/OIDC、多租户和复杂 BI 仍未全量完成。
- `go_no_go`：仅给人工复核建议，不自动改变既有 Go/No-Go 结论。
- `next_actions`：根据 skipped/blocked/partial 来源给出后续补证和人工复核动作。
- `boundary_declarations`：声明只读、默认 fake/offline、不执行真实外网 LLM、不输出 secret、不打 tag、不创建 Release。

## CLI 示例

```powershell
python scripts/pilot_closeout_report_pack.py `
  --pilot-handoff docs/reports/pilot_handoff/example.json `
  --evidence-archive docs/reports/evidence_archive/example.json `
  --integration-readiness docs/reports/optional_integration_readiness/example.json `
  --operator-scoring docs/reports/operator_drill_scoring/example.json `
  --controlled-integration docs/reports/controlled_integration_dry_run/example.json `
  --governance-exceptions docs/reports/governance_exceptions/example.json
```

## 边界

- 只读：只写 `--output-dir` 下的报告包，不写业务数据。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- 不执行真实外网 LLM，不连接真实外部 MCP。
- 不读取或输出真实 secret 原文。
- 不修改 `.env` 或环境变量。
- 不打 tag，不创建 GitHub Release，不移动历史 tag。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。

## 验证

```powershell
python -m pytest tests/test_pilot_closeout_report_pack_v355.py -q
```

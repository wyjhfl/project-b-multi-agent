# 生产落地预提交收口摘要

## 目标

`scripts\production_landing_precommit_closeout.py` 用于最终总结提交前的本地收口判断。它只读取结构化 JSON 证据，不连接真实业务系统，不调用真实 LLM，不执行 migration，不写业务数据、审计数据或指标数据，不读取或输出 secret 原文。

该脚本回答一个问题：当前工作区在尚未提交的情况下，是否已经具备可进入最终人工复核和提交收口的证据。

## 正常预提交状态

当以下条件满足时，脚本输出 `precommit_landing_ready=true`：

- `production_landing_action_pack` 为 `success` 且 `required_input_count=0`
- Postgres、Redis、external MCP 当前轮 infra smoke 为 `success`
- 文本质量检查为 `success`
- run packet 只因为 evidence freshness 等待提交而保持 `Manual-Review`
- `public_production_direct_launch=No-Go`
- `secret_plaintext_output=false`

允许的预提交缺口只有：

- `controlled_pilot_operator_packet:production_landing_evidence_freshness:not_fresh`
- `controlled_pilot_run_packet:required_ready_evidence_not_satisfied`

这些缺口表示当前工作区尚未提交；提交后需要重新刷新 evidence freshness 和 run packet。

## 执行命令

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\production_landing_precommit_closeout.py
```

默认输出：

- `docs/reports/production_landing_precommit_closeout/*.json`
- `docs/reports/production_landing_precommit_closeout/*.md`

## 边界

- `post_commit_required=true` 表示提交后必须重新刷新证据 freshness。
- `business_system:real_business_system_required` 仍是真实生产缺口。
- 该收口不等于公网生产直接上线。
- 不得把 demo read-only 业务系统包装成真实业务系统生产验收完成。
- `public_production_direct_launch=No-Go` 必须保持不变。

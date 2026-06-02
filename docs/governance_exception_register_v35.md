# v3.5 Phase 15.4 Governance Exception Register Runbook

## 目标

Phase 15.4 建立治理例外登记册，用于记录企业内网受控试点中暂时无法关闭、但需要人工评审和持续跟踪的治理例外候选项。登记册覆盖风险描述、影响范围、责任人、到期时间、补偿控制、复核证据、状态和下一步动作，避免口头豁免无法追踪。

本 runbook 定义只读汇总口径和输出结构。它不自动批准例外，不绕过 deployment guard、安全响应头、审计脱敏或审批链路，不代表生产安全豁免，也不代表公网生产可直接上线。

## 输入来源

推荐从以下只读 JSON 摘要读取状态、缺失条件、告警和证据路径：

- 配置漂移检查：`docs/reports/config_drift/`
- 治理策略摘要：`docs/reports/governance_policy/`
- 故障演练包：`docs/reports/incident_rehearsal/`
- 操作员演练评分：`docs/reports/operator_drill_scoring/`
- 受控集成 dry-run：`docs/reports/controlled_integration_dry_run/`

输入只消费结构化 JSON 元数据，例如 `status`、`missing_conditions`、`warnings`、`recommended_actions`、`boundary_declarations` 和来源路径。不得读取报告正文，不得解析 prompt 原文、secret 原文、连接串密码原文或业务数据正文。

## 默认输出目录

- `docs/reports/governance_exceptions/`

输出建议包含 JSON 登记册与 Markdown 摘要。Markdown 摘要用于人工评审，不作为自动批准依据。

## 推荐命令

默认生成空输入场景下的只读登记册：

```powershell
python scripts/governance_exception_register.py --output-dir docs/reports/governance_exceptions
```

指定上游 JSON 摘要时：

```powershell
python scripts/governance_exception_register.py `
  --config-drift docs/reports/config_drift/latest.json `
  --governance-policy docs/reports/governance_policy/latest.json `
  --incident-report docs/reports/incident_rehearsal/latest.json `
  --operator-scoring docs/reports/operator_drill_scoring/latest.json `
  --controlled-integration docs/reports/controlled_integration_dry_run/latest.json `
  --output-dir docs/reports/governance_exceptions
```

命令语义必须保持只读：不启动服务、不修改 `.env`、不写业务数据、不调用真实外网 LLM、不连接真实外部 MCP、不自动批准例外。

## 例外字段

每条例外候选项建议包含：

- `exception_id`：稳定登记编号。
- `source`：来源报告标识。
- `risk_description`：脱敏后的风险描述。
- `scope`：影响范围，例如 config、security、operations、integration、evidence。
- `owner`：责任人占位，默认 `manual_owner_required`。
- `expires_at`：到期时间占位，默认 `manual_expiry_required`。
- `compensating_controls`：补偿控制占位或建议。
- `review_evidence`：来源 JSON 路径和证据字段名。
- `status`：例外状态。
- `next_actions`：下一步人工动作。
- `approval_state`：固定为 `not_approved`，除非后续人工流程另行批准。

## 状态词

### 顶层状态

- `success`：登记册生成成功，所有输入可解释，未发现阻断项。`success` 只代表登记流程成功，不代表例外已获批准。
- `skipped`：未提供输入、输入目录为空或本轮无例外候选项；必须记录原因。
- `blocked`：发现疑似 secret 原文、输入不可解析、只读边界冲突或上游报告显示真实外部执行风险。
- `partial`：部分输入可用，部分输入缺失、 skipped 或有非致命告警。
- `failed`：脚本异常或输出不可用。

### 例外状态

- `pending_review`：需要人工评审，默认状态。
- `skipped`：来源缺失或本轮无需登记，但保留原因。
- `blocked`：存在 secret、只读边界或真实外部执行风险，需先关闭阻断项。
- `expired`：人工填写到期时间后已过期；脚本默认不自动推断。
- `closed`：人工后续关闭；脚本默认不自动关闭。

强约束：脚本不得生成 `approved` 状态，不得自动批准例外，不得把 `skipped/blocked` 伪造成 `success`。

## 输出字段

建议输出字段如下：

- `generated_at`：生成时间，ISO8601。
- `commit`：当前提交哈希，无法获取时为 `unknown`。
- `version`：当前应用版本；v3.5 release prep 后为 `3.5.0`。
- `mode`：`fake_offline_default`。
- `status`：顶层状态。
- `read_only`：固定为 `true`。
- `real_llm_executed`：固定为 `false`。
- `external_mcp_connected`：固定为 `false`。
- `service_started`：固定为 `false`。
- `auto_approved`：固定为 `false`。
- `input_sources`：输入路径、存在性、加载状态和摘要状态。
- `exception_register`：例外候选项列表。
- `exception_count`：候选项数量。
- `missing_conditions`：缺失条件列表。
- `warnings`：非致命告警列表。
- `recommended_actions`：人工后续动作。
- `boundary_declarations`：只读、secret、真实 LLM、MCP、审批与生产声明边界。

## 只读边界

- 不启动服务，不修改配置，不写业务数据。
- 不调用真实外网 LLM。
- 不连接真实外部 MCP Server。
- 不默认启用 auth、RBAC、Redis 或 Postgres。
- 不绕过 deployment guard、安全响应头、审计脱敏或审批链路。
- 不删除、移动、重命名、清理或归档任何既有报告文件。
- 不移动、删除、重建任何历史 tag。
- 仅允许将登记册摘要写入 `docs/reports/governance_exceptions/`。

## Secret 边界

- 禁止输出任何密钥、Token、API Key、client_secret、JWT_SECRET、DATABASE_URL、REDIS_URL 或连接串密码原文。
- 如需要表达配置存在性，仅输出 env name 与 `present=true/false`，不得输出真实值。
- 不输出 prompt 原文、审计日志敏感正文、用户业务数据正文或外部系统凭证。
- 如输入中疑似包含 secret 原文，状态应标记为 `blocked`，并只记录脱敏后的风险说明。

## 与上游能力的关系

- `config drift` 提供配置漂移和模板键差异，登记册只消费其摘要，不修改 `.env`。
- `governance policy summary` 提供治理边界证据，登记册不替代治理策略本身。
- `incident rehearsal` 提供故障演练状态，登记册不重新演练故障。
- `operator drill scoring` 提供复盘评分，登记册不自动改变 Go/No-Go。
- `controlled integration dry-run` 提供可选集成缺失条件，登记册保留 `skipped/blocked` 语义，不伪造成通过。

## Go/No-Go 口径

- 企业内网受控试点可继续：登记册生成 `success` 或可解释的 `partial`，无 secret 原文输出，无边界违规，所有候选例外均为 `pending_review` 或 `skipped`，且没有自动批准。
- 继续观察或补证：顶层状态为 `skipped` 或 `partial`，输入缺失或候选例外缺少 owner/expiry，需要人工补齐。
- No-Go：顶层状态为 `blocked/failed`、发现 secret 原文输出、执行真实外网 LLM、连接真实外部 MCP、写业务数据、自动批准例外、绕过审批或隐藏 `skipped/blocked`。

本登记册不宣称公网生产可直接上线，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC、多租户或复杂 BI 全量完成。最终 Go/No-Go 仍需人工结合 release review、security review、pilot handoff 和试点上下文确认。

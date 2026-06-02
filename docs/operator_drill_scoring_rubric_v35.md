# v3.5 Phase 15.2 Operator Drill Scoring Rubric Runbook

## 目标

Phase 15.2 面向企业内网试点的操作员演练复盘，建立一套只读评分口径，用于把 incident rehearsal、pilot handoff、optional integration readiness、evidence comparison 等既有证据转化为可解释的演练评分摘要。

本 runbook 只定义评分维度、输入来源、输出字段和边界约束。评分结果用于辅助复盘和人工评审，不自动改变 Go/No-Go 结论，不把 `skipped` 或 `blocked` 伪造成 `success`。

## 输入来源

推荐从以下只读证据或摘要中取数：

- 故障演练包：`docs/reports/incident_rehearsal/`
- 试点交接清单：`docs/reports/pilot_handoff/`
- 可选集成准备度矩阵：`docs/reports/optional_integration_readiness/`
- 证据对比快照：`docs/reports/pilot_evidence_comparison/`
- 运营工作流索引：`docs/reports/operator_workflow/`
- 证据归档 manifest：`docs/reports/evidence_archive/`

输入应优先使用 JSON 摘要、manifest 或脚本输出的元数据字段。不得读取报告正文内容，不得解析 prompt 原文、secret 原文、连接串密码原文或业务数据正文。

## 默认输出目录

- `docs/reports/operator_drill_scoring/`

## 推荐命令

规划命令如下，供后续脚本实现或人工复盘时保持一致：

```powershell
python scripts/operator_drill_scoring.py --output-dir docs/reports/operator_drill_scoring
```

指定输入 JSON 报告时：

```powershell
python scripts/operator_drill_scoring.py `
  --incident-report docs/reports/incident_rehearsal/latest.json `
  --handoff-report docs/reports/pilot_handoff/latest.json `
  --integration-readiness docs/reports/optional_integration_readiness/latest.json `
  --evidence-comparison docs/reports/pilot_evidence_comparison/latest.json `
  --output-dir docs/reports/operator_drill_scoring
```

脚本只读取 JSON 元数据字段，不读取 Markdown 报告正文；输入缺失或为空时输出 `skipped` 并记录缺失条件。

## 评分维度

建议使用 0 到 5 分制，并保留无法评分原因：

| 维度 | 脚本字段 | 评分关注点 | 低分或阻断示例 |
|------|----------|------------|----------------|
| 可用性 | `availability` | incident rehearsal 是否识别 service unavailable、compose、guard、OIDC、real LLM opt-in 等场景 | blocked 未解释、failed 无后续建议 |
| 可恢复性 | `recoverability` | incident rehearsal 与 pilot handoff 是否保留恢复路径和交接证据 | 关键输入缺失、缺少 skipped 原因 |
| 证据完整性 | `evidence_integrity` | evidence comparison 是否能说明新增、减少、变化文件统计 | baseline/current 缺失却伪造成 success |
| 配置准备度 | `configuration_readiness` | optional integration readiness 是否清楚标记 real LLM、OIDC、external MCP、Postgres、Redis 等可选项 | 缺少 opt-in 条件却标记成功 |
| 权限边界 | `permission_boundary` | pilot handoff 与 readiness 是否保留 RBAC、审批和启用边界 | 未说明默认关闭或审批边界 |
| 已知限制 | `known_limitations` | pilot handoff 是否覆盖公网直上 No-Go、真实生产验收需另行执行等限制 | 未说明公网直上 No-Go |

总分可作为辅助指标，但不得替代状态词和人工 Go/No-Go 评审。若任一边界合规性检查触发严重问题，总分不应掩盖该问题。

## 状态词

- `success`：输入证据可读取，评分维度完整，未发现边界违规，且 warnings 不影响复盘可用性。
- `skipped`：缺少可选输入、服务未启动、目录为空或本轮未请求某项评分；必须记录缺失条件列表。
- `blocked`：缺少必需输入或存在无法继续评分的前置问题，需要人工处理后重跑。
- `partial`：部分输入可用，部分输入缺失或存在非致命 warnings，评分可辅助复盘但不能作为完整结论。
- `failed`：评分流程异常或输出不可用。

强约束：`skipped` 和 `blocked` 是有效状态，不得伪造成 `success`；缺少 opt-in 条件、缺少 baseline/current 或空目录时必须明确记录原因。

## 输出字段

建议输出 JSON 与 Markdown 摘要，字段包括：

- `generated_at`：生成时间，ISO8601。
- `version`：当前应用版本；v3.5 release prep 前保持 `3.4.0`。
- `status`：顶层状态词。
- `read_only`：固定为 `true`。
- `real_llm_executed`：固定为 `false`。
- `output_dir`：输出目录。
- `input_sources`：输入目录或 manifest 路径列表。
- `dimension_scores`：各维度分数、状态、证据来源和说明。
- `overall_score`：归一化总分。
- `risk_level`：`low / medium / high` 风险等级。
- `missing_conditions`：缺失条件列表。
- `warnings`：非致命告警列表。
- `recommended_actions`：建议后续人工动作。
- `boundary_declarations`：只读、隐私、secret、真实 LLM 边界声明。

## 只读边界

- 不读取报告正文，仅读取 JSON 摘要、manifest、目录与文件元数据。
- 不写业务数据，仅写评分摘要到 `docs/reports/operator_drill_scoring/`。
- 不删除、移动、重命名、清理或归档任何报告文件。
- 不修改 `.env`、环境变量、配置模板或数据库。
- 不启动真实外部 MCP Server。
- 不执行真实外网 LLM。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。

## 隐私与 Secret 边界

- 不读取或输出真实 secret 原文，包括 API key、Token、client_secret、JWT_SECRET、DATABASE_URL、REDIS_URL。
- 不输出 prompt 原文、连接串密码原文或用户业务数据正文。
- 输出中只允许出现配置项名称、布尔状态、缺失条件、脱敏路径或文件元数据。
- 如发现输入疑似包含 secret 原文，应将状态标记为 `blocked` 或 `failed`，并只记录脱敏后的风险说明。

## 与相关能力的关系

- `incident rehearsal` 提供故障场景覆盖和状态来源，评分只消费其摘要，不重新演练故障。
- `pilot handoff` 提供角色、权限、交接证据和已知限制，评分用于检查交接可执行性，不替代交接确认。
- `optional integration readiness` 提供 real LLM、OIDC、external MCP、Postgres、Redis 等可选集成准备度，评分不触发真实外部连接。
- `evidence comparison` 提供 baseline/current 证据变化视角，评分不读取报告正文，也不替代 evidence archive manifest。

推荐复盘顺序：先生成或确认 incident rehearsal、optional integration readiness、pilot handoff 与 evidence comparison，再执行 operator drill scoring，最后由人工评审 Go/No-Go。

## Go/No-Go 口径

- 企业内网试点 Go：评分状态为 `success` 或可解释的 `partial`，无 secret 泄漏，无边界违规，无伪成功，且关键缺失条件已有人工确认。
- 继续观察或补证：状态为 `skipped` 或 `partial`，但缺失项属于可选输入或本轮未请求范围，并已记录 `missing_conditions`。
- No-Go：状态为 `failed`、不可解释的 `blocked`、发现 secret 原文输出、读取报告正文、写业务数据、执行真实外网 LLM、伪造 `success`，或把 skipped/blocked 隐去。

本评分摘要不自动改变 Go/No-Go 结论。最终 Go/No-Go 仍需由人工结合 release review、handoff、security review 和试点上下文确认。

保持统一边界：不宣称公网生产可直接上线，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC、多租户或复杂 BI 全量完成。

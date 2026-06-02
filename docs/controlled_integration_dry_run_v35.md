# v3.5 Phase 15.3 Controlled Integration Dry-run Checklist Runbook

## 目标

Phase 15.3 建立受控集成干跑清单，用于在企业内网试点扩大前，对 real LLM、OIDC、external MCP、Postgres、Redis、frontend build、deployment guard、audit export redaction 等可选集成项进行只读预检和证据归档。

本 runbook 只定义干跑目标、输入来源、输出字段、状态词和边界口径。它不执行真实外部集成，不自动改变 Go/No-Go 结论，不把缺少 opt-in 条件的项目伪造成 `ready` 或 `success`。

## 输入来源

推荐从以下只读来源读取 JSON 摘要、manifest 或本地可验证元数据：

- 可选集成准备度矩阵：`docs/reports/optional_integration_readiness/`
- 配置漂移检查：`docs/reports/config_drift/`
- 部署门禁或本地 deployment guard 检查输出
- 审计导出与脱敏边界检查输出
- 前端构建或依赖预检的本地结果
- OIDC 最小演练记录或配置预检结果
- external MCP fake/fixture readiness 记录
- Postgres、Redis、auth/RBAC 相关配置存在性检查结果

输入应优先使用结构化 JSON 字段、文件元数据、目录存在性和配置项存在性判断。不得读取真实 secret 值，不得解析 prompt 原文、连接串密码原文、业务数据正文或报告正文。

## 默认输出目录

- `docs/reports/controlled_integration_dry_run/`

输出建议包含 JSON 摘要与 Markdown 摘要。Markdown 摘要只呈现脱敏后的状态、缺失条件、建议动作和边界声明。

## 推荐命令

规划命令如下，供后续脚本实现或人工复核时保持一致：

```powershell
python scripts/controlled_integration_dry_run.py --output-dir docs/reports/controlled_integration_dry_run
```

串联 Phase 14.4 optional integration readiness JSON 时：

```powershell
python scripts/controlled_integration_dry_run.py `
  --readiness-report docs/reports/optional_integration_readiness/latest.json `
  --output-dir docs/reports/controlled_integration_dry_run
```

该命令语义必须保持只读：不启动服务、不修改 `.env`、不启用真实集成、不连接真实外部 MCP、不调用真实外网 LLM。

## 覆盖集成项

| 集成项 | 干跑检查重点 | 默认边界 |
|------|------------|----------|
| real LLM | opt-in 环境变量是否存在、provider 配置是否具备本地预检条件、预算和 fallback 字段是否可解释 | 默认不调用真实外网 LLM；缺少 opt-in 条件必须 `skipped` |
| OIDC | issuer、client id、client secret env name、redirect 配置、auth/RBAC 开关意图是否一致 | 默认不启用 auth/RBAC；不连接真实 IdP；不输出 client secret 值 |
| external MCP | mode、command、allowlist、fake/fixture 验收记录是否存在 | 默认不连接真实外部 MCP；缺少显式 real mode 条件必须 `skipped` |
| Postgres | `STORAGE_BACKEND`、`DATABASE_URL` env name 是否存在、迁移门禁是否有记录 | 默认不启用 Postgres；不输出连接串值 |
| Redis | `REDIS_ENABLED`、`REDIS_URL` env name 是否存在、Noop fallback 口径是否保留 | 默认不启用 Redis；不连接 Redis；不输出连接串值 |
| frontend build | 前端构建依赖、网络依赖、构建命令记录是否存在 | 不默认安装或拉取新依赖；网络依赖缺失可 `skipped` |
| deployment guard | 生产门禁是否输出结构化结果、错误是否可解释 | 不启动生产服务；不把配置缺失伪造成通过 |
| audit export redaction | 审计导出是否默认脱敏、是否避免 prompt 原文和 secret 原文 | 不读取或输出审计正文中的敏感原文 |

## 状态词

### 集成项状态

- `ready`：本地可验证配置存在性和预检条件满足，且没有触发边界违规。`ready` 不代表真实生产验收完成。
- `skipped`：缺少 opt-in 条件、输入目录为空、服务未启动、真实外部依赖未配置或本轮未请求该集成项；必须记录 `missing_conditions`。
- `blocked`：发现无法继续干跑的前置问题，例如疑似 secret 原文泄漏、输入结构不可解析、边界声明冲突或必需证据缺失。
- `partial`：部分条件满足，部分条件缺失；可用于人工复核，但不得作为完整 ready 结论。

### 顶层状态

- `success`：干跑流程完成，所有必查集成项均为 `ready` 或有清晰解释的 `skipped`，无 secret 泄漏、无边界违规、无伪成功。
- `skipped`：本轮缺少必要输入或全部集成项均因 opt-in 不完整而跳过；必须记录缺失条件列表。
- `blocked`：存在需人工处理后才能继续的边界或输入问题。
- `partial`：部分集成项可解释，部分集成项缺少输入或存在非致命告警。
- `failed`：脚本异常、输出不可用或结果无法解释。

强约束：缺少 opt-in 条件必须标记为 `skipped`，不得伪造成 `ready` 或 `success`；`skipped` 和 `blocked` 是有效状态，不应被隐藏。

## 输出字段

建议输出字段如下：

- `generated_at`：生成时间，ISO8601。
- `version`：当前应用版本；v3.5 release prep 前保持既有版本口径。
- `status`：顶层状态词，取值为 `success/skipped/blocked/partial/failed`。
- `output_dir`：输出目录。
- `read_only`：固定为 `true`。
- `real_llm_executed`：固定为 `false`。
- `external_mcp_connected`：固定为 `false`。
- `service_started`：固定为 `false`。
- `default_auth_enabled`：固定说明默认不启用 auth。
- `default_rbac_enabled`：固定说明默认不启用 RBAC。
- `default_postgres_enabled`：固定说明默认不启用 Postgres。
- `default_redis_enabled`：固定说明默认不启用 Redis。
- `input_sources`：输入目录、文件路径或 manifest 路径列表。
- `integrations`：各集成项状态、缺失条件、告警和建议动作。
- `env_presence`：仅输出 env name 与 `present=true/false`，不得输出真实值。
- `missing_conditions`：缺失条件列表。
- `warnings`：非致命告警列表。
- `recommended_actions`：后续人工动作建议。
- `go_no_go_hint`：只提供辅助口径，不自动改变 Go/No-Go 结论。
- `boundary_declarations`：只读、secret、真实 LLM、external MCP、auth/RBAC、Postgres、Redis 边界声明。

## 只读边界

- 不启动服务，不启动生产部署，不执行真实外部集成。
- 不调用真实外网 LLM。
- 不连接真实外部 MCP Server。
- 不默认启用 auth、RBAC、Redis 或 Postgres。
- 不修改 `.env`、环境变量、配置模板、数据库、缓存或业务数据。
- 不删除、移动、重命名、清理或归档任何既有报告文件。
- 不移动、删除、重建任何历史 tag。
- 仅允许将干跑摘要写入 `docs/reports/controlled_integration_dry_run/`。

## Secret 边界

- 禁止输出任何密钥、Token、API Key、client_secret、JWT_SECRET、DATABASE_URL、REDIS_URL 或连接串密码原文。
- 对环境变量只输出 env name 与 `present=true/false`。
- 不输出 prompt 原文、审计日志中的敏感正文、用户业务数据正文或外部系统凭证。
- 如输入中疑似包含 secret 原文，状态应标记为 `blocked` 或 `failed`，并只记录脱敏后的风险说明。
- `.env` 文件仅可作为配置存在性边界的来源；不得复制或展示其中的真实值。

## 与 Optional Integration Readiness 的关系

`optional integration readiness` 是 Phase 14.4 的可选集成准备度矩阵，关注配置存在性与本地可验证条件。Phase 15.3 的 controlled integration dry-run 在此基础上形成干跑清单和 Go/No-Go 辅助口径：

- 继承其集成项范围：real LLM、OIDC、external MCP、Postgres、Redis、frontend build、deployment guard、audit export redaction。
- 复用其只读边界：不调用真实 LLM、不连接真实 MCP、不要求默认启用 auth/RBAC/Redis/Postgres。
- 强化状态语义：缺少 opt-in 条件时必须 `skipped`，不得伪造成 `ready/success`。
- 增加干跑输出字段、缺失条件汇总、边界声明和 Go/No-Go 辅助说明。

该干跑不替代 optional integration readiness，也不替代真实生产验收。它只把已有准备度、配置漂移、部署门禁、审计脱敏等证据整理成可复核的只读清单。

## Go/No-Go 口径

- 企业内网受控试点 Go：顶层状态为 `success` 或可解释的 `partial`，无 secret 原文输出，无边界违规，无伪成功；关键 skipped 条件已有人工确认且不影响本轮试点范围。
- 继续观察或补证：顶层状态为 `skipped` 或 `partial`，缺失项属于可选真实集成或本轮未 opt-in 范围，并已明确记录 `missing_conditions`。
- No-Go：顶层状态为 `failed`、不可解释的 `blocked`、发现 secret 原文输出、执行真实外网 LLM、连接真实外部 MCP、默认启用 auth/RBAC/Redis/Postgres、写业务数据、修改 `.env`、伪造 `ready/success`，或隐藏 `skipped/blocked`。

本 runbook 不宣称公网生产可直接上线，不宣称真实 LLM 生产验收完成，不宣称生产级 SSO/OIDC、多租户或复杂 BI 全量完成。最终 Go/No-Go 仍需结合 release review、security review、pilot handoff 和试点上下文由人工确认。

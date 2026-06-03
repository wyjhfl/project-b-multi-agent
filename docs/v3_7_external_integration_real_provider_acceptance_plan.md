# v3.7 External Integration & Real Provider Acceptance 规划

## 定位

- v3.7 = **External Integration & Real Provider Acceptance**。
- 核心目标：在 v3.6 已完成身份、权限、租户边界和跨租户审计证据准备后，进入真实外部 MCP、真实 LLM provider、PostgreSQL、Redis 和业务系统集成的受控验收准备。
- 当前先进入规划与只读基线阶段，默认版本保持 `3.6.0`。
- 本轮不打 tag、不创建 GitHub Release、不移动历史 tag。

## 当前基线

- `v3.6.0` release prep 已完成，本地提交已创建；由于当前环境 GitHub HTTPS 推送不可用，远端同步需网络恢复后执行。
- MCP stdio real protocol path 已具备最小协议链路，但默认仍为 `MCP_MODE=fake`。
- LiteLLMProvider、LLMJudgeProvider、real LLM preflight/smoke/report 已具备 opt-in 骨架，但默认不调用真实外网 LLM。
- PostgreSQL Store、Redis 配置、NoopRedisClient fallback、deployment guard 和 prod compose override 已具备工程化基础。
- 前端已移除构建期 Google Fonts 依赖，默认离线 build 可通过。

## 边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 默认不连接真实外部 MCP、不连接真实业务系统。
- 不默认启用真实 provider、真实写入集成或真实外部网络验收。
- 不读取或输出真实 secret 原文。
- 不绕过 ToolGateway、PolicyEngine、审批链路或审计链路。
- 不把 fake fixture、opt-in smoke 或只读 dry-run 宣称为生产验收完成。
- 不宣称公网生产可直接上线，不宣称真实 LLM 生产验收完成。

## 阶段优先级

- P0：Phase 17.1、Phase 17.2。
- P1：Phase 17.3、Phase 17.4。
- P2：Phase 17.5、Phase 17.6。

## Phase 17.1：External integration baseline inventory（P0）

### 目标

建立真实外部集成与 provider 验收前的只读基线盘点，明确当前 MCP、LLM、Judge、PostgreSQL、Redis、deployment guard、审批审计和前端离线构建的现状与缺口。

### 修改范围

- 新增 runbook：`docs/external_provider_acceptance_inventory_v37.md`。
- 新增只读脚本：`scripts/external_provider_acceptance_inventory.py`。
- 新增测试：`tests/test_external_provider_acceptance_inventory_v371.py`。
- 默认输出目录：`docs/reports/external_provider_acceptance_inventory/`。

### 不做什么

- 不连接真实外部 MCP。
- 不调用真实外网 LLM。
- 不连接真实业务系统。
- 不执行真实数据库迁移或 Redis 写入。
- 不读取或输出真实 secret 原文。

### 验证命令

```powershell
python -m pytest tests/test_external_provider_acceptance_inventory_v371.py -q
python -m pytest tests/test_mcp_stdio_client_v31.py tests/test_llm_provider_v41.py tests/test_storage_v20.py -q
docker compose config
```

### 完成标准

- 输出覆盖 external MCP、real LLM provider、LLM judge、PostgreSQL、Redis、deployment guard、tool approval audit、frontend offline build。
- 缺少 opt-in 条件时记录为 `skipped` 或 `partial`，不得伪造成 `success`。
- 输出明确 `read_only=true`、`real_llm_executed=false`、`external_mcp_connected=false`、`business_system_connected=false`。
- 仅输出 env name 与 `present=true/false`，不输出真实 secret 值。

## Phase 17.2：External MCP acceptance gate（P0）

### 目标

建立真实外部 MCP 验收门禁，覆盖 command allowlist、tool allowlist、超时、stderr 边界、生命周期、审批与审计。

### 计划交付

- MCP acceptance gate runbook。
- 只读 preflight 脚本。
- fake fixture 与 real mode opt-in 的语义拆分测试。

### 完成状态

- 本阶段交付物已落地：`docs/external_mcp_acceptance_gate_v37.md`、`scripts/external_mcp_acceptance_gate.py`、`tests/test_external_mcp_acceptance_gate_v372.py`。
- 输出明确 `external_mcp_connected=false`、`mcp_process_started=false`、`mcp_tools_list_executed=false`、`mcp_tools_call_executed=false`。
- 本阶段不启动 MCP subprocess，不执行真实 `tools/list` 或 `tools/call`，不宣称真实外部 MCP 生产验收完成。

## Phase 17.3：Real LLM provider acceptance gate（P1）

### 目标

建立真实 LLM provider 验收门禁，覆盖 preflight、smoke、budget、cache、fallback、PII 脱敏、prompt injection guard、输出校验和报告脱敏。

### 计划交付

- real provider acceptance gate runbook。
- 只读验收摘要脚本。
- opt-in smoke 证据索引与 blocked/skipped 语义复核。

## Phase 17.4：Store and Redis production readiness drill（P1）

### 目标

建立 PostgreSQL Store 与 Redis 的生产准备演练，覆盖连接失败、迁移预检、Noop fallback、限流存储、审计与指标双写边界。

### 计划交付

- store/redis readiness drill runbook。
- 只读配置与迁移清单脚本。
- storage/redis/deployment guard 定向回归。

## Phase 17.5：Business system integration safety checklist（P2）

### 目标

建立真实业务系统集成前的安全清单，覆盖只读/写入边界、幂等、失败恢复、回滚证据、审批和审计。

### 计划交付

- business integration safety checklist。
- tool gateway/policy/approval/audit 证据模板。
- 写入集成默认禁用和 opt-in 审批口径。

## Phase 17.6：v3.7 release prep（P2）

### 目标

完成 v3.7 release prep，同步版本号、release notes、release review 和 tag 决策前复核材料。

### 不做什么

- release prep 当轮不打 tag。
- release prep 当轮不创建 GitHub Release。
- 不移动、删除或重建历史 tag。
- 不执行真实外网 LLM。
- 不宣称真实外部 MCP、真实 LLM 或业务系统生产验收完成。

# v3.1 Phase 11.1：Demo E2E Runbook（离线演示）

## 1. 目标

- 提供可重复执行的离线演示数据与端到端演示脚本。
- 在默认 fake/offline 路径下完成健康检查、数据准备、核心 API smoke、前端演示提示。
- 保持安全边界：不调用真实外网 LLM、不依赖真实外部 MCP、不输出密钥原文。

## 2. 前置条件

- 代码仓库：`project-b-multi-agent`
- Python 环境可用
- Docker 可用（用于 `docker compose config` 与可选容器启动）
- 默认配置保持：
  - `REAL_LLM_ACCEPTANCE_ENABLED=false`
  - `MCP_MODE=fake`

## 3. 主要文件

- `scripts/demo_seed_data.py`：生成 v3.1 演示 seed 数据
- `scripts/demo_e2e.ps1`：端到端演示脚本
- `docs/demo_fixtures/trace_demo_events_v31.json`：离线 trace 演示 fixture（由 seed 脚本写入）
- `docs/reports/real_llm_pilot/`：离线 pilot report 演示文件（由 seed 脚本运行时生成，默认不入库）

## 4. 执行命令

### 4.1 仅准备演示数据

```powershell
python scripts/demo_seed_data.py
```

说明：

- 该命令会初始化/覆盖 demo 数据（按脚本定义的幂等策略清理旧 demo 前缀数据后写入新数据）。
- 不写入真实密钥，不包含 prompt 原文。
- 命令输出会返回 report json/md 路径，供演示后人工审查（脱敏内容）。

### 4.2 端到端演示（推荐）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo_e2e.ps1
```

可选参数：

- `-BaseUrl http://localhost:8000`：后端地址
- `-SkipSeed`：跳过 seed 步骤，仅做在线 smoke

## 5. 预期输出

- 脚本输出包含：
  - `mode=fake_offline`
  - `real_llm=disabled`
  - `mcp_mode=fake`
  - seed 步骤状态（`ok` 或 `skipped`）
  - 在线 smoke 步骤状态

### 服务未启动时

- 脚本应输出：
  - `online_smoke status=skipped reason=service_unavailable`
  - 明确提示如何启动服务
- 该场景不应误报成功，不应抛出误导性“全部通过”。

### 服务已启动时

- 脚本应检查核心端点：
  - `/health`
  - `/tasks`
  - `/approvals`
  - `/audit/events`
  - `/metrics/runtime`
  - `/llm/pilot/reports`
  - `/operations/summary`
  - `/nl2sql/preview`（mock/fake）
- 并输出前端访问提示（`http://localhost:3000`），可进入 `/operations` 查看只读运营总览。

## 6. 演示数据范围（seed）

- 任务：keyword / nl2sql / waiting_approval 示例
- 审批：高风险 pending 审批示例
- 审计：demo 事件示例
- 指标：task/tool/token 使用示例
- NL2SQL：mock/fake 结果示例
- Pilot evidence：离线脱敏报告示例
- Trace：只读 fixture 示例

约束：

- 不包含真实用户隐私
- 不包含真实密钥
- 不包含 prompt 原文

## 7. 常见失败与处理

- `python scripts/demo_seed_data.py` 失败：
  - 检查 Python 环境与仓库路径。
- `demo_e2e.ps1` 在线 smoke skipped：
  - 先启动服务（例如 `docker compose up -d app frontend`）后重试。
- `/nl2sql/preview` 失败：
  - 确认默认 `generator=mock`、`provider=fake` 配置未被改动。

## 8. 清理与回滚

- 容器清理：
  - `powershell -ExecutionPolicy Bypass -File scripts/demo_down.ps1`
- 演示数据重置：
  - 重新执行 `python scripts/demo_seed_data.py`（会清理并重建 demo 前缀数据）
- 不删除业务历史数据文件；若涉及手工清理，先备份后处理。

## 9. 边界声明

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 真实 LLM 仅 opt-in，不在本 runbook 默认路径执行。
- 不提交密钥，不输出 token/password/DSN 密码原文。
- 不宣称公网生产可直接上线。

## v3.2 Phase 12.3 add-on (Demo artifact bundle)

- command supports `-ArtifactDir`:
  - `powershell -ExecutionPolicy Bypass -File scripts/demo_e2e.ps1 -ArtifactDir docs/reports/demo_artifacts`
- each run creates a timestamped folder and writes:
  - `demo_e2e_summary.json`
  - `online_smoke_result.json`
  - `seed_summary.json`
  - `pilot_report_index.json`
  - `acceptance_snapshot/*.json` and `*.md`
- see details: `docs/demo_artifact_bundle_runbook_v32.md`

# v3.3 Operational Automation & Governance 规划

## 1. 阶段定位

- v3.3 定位：**Operational Automation & Governance**。
- 目标：将 v3.2 的 acceptance snapshot、demo artifact bundle、failure diagnostics、operations overview 沉淀为可重复运维自动化与治理流程。
- 保留历史发布事实：`v3.2.0` / `v3.1.0` / `v3.0.0` tag 与对应发布记录保持不变。
- 当前版本仍为 `3.2.0`（本阶段不改版本号、不打 tag、不创建 Release）。

## 2. 边界声明

- 不等于公网生产直接上线。
- 不等于真实 LLM 生产验收完成。
- 不等于生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- 真实 LLM 仅 opt-in；无 opt-in 条件时必须 skipped 归档。
- 不提交密钥/token/client_secret/JWT_SECRET/DATABASE_URL/REDIS_URL 明文。

## 3. 建议 Phase（13.1 ~ 13.6）

### Phase 13.1：Report index & retention（P0）

- 目标：
  - 为 acceptance snapshots / demo artifacts / failure diagnostics 建立只读索引。
  - 明确保留策略边界（文档或最小只读 API）。
- 修改范围：
  - docs + 可选只读聚合入口（不写业务数据）。
- 不做什么：
  - 不删除用户数据，不做破坏性清理。
- 验证命令：
  - `python -m pytest tests/test_runtime_hardening_v055.py -q`
  - `docker compose config`
- 完成标准：
  - 索引可读、路径可追踪、保留策略边界明确。

当前状态（2026-05-29）：

- 已新增脚本：`scripts/report_index.py`
- 已新增测试：`tests/test_report_index_v331.py`
- 已新增 runbook：`docs/report_index_retention_runbook_v33.md`
- 默认索引输出：`docs/reports/report_index/`
- 仅列出 stale candidates，不执行删除动作

### Phase 13.2：Config drift checklist（P0）

- 目标：
  - 为 `.env.example` / `.env.production.example` / deployment guard / runtime settings 建立配置漂移检查清单。
  - 可选输出只读 JSON/Markdown 检查结果。
- 修改范围：
  - checklist 文档 + 可选只读脚本。
- 不做什么：
  - 不自动改配置，不写入真实凭据。
- 验证命令：
  - `python -m pytest tests/test_runtime_hardening_v055.py -q`
  - `docker compose config`
- 完成标准：
  - 可重复检查 drift 项，输出清晰可审计。

当前状态（2026-05-29）：

- 已新增脚本：`scripts/config_drift_check.py`
- 已新增测试：`tests/test_config_drift_v332.py`
- 已新增清单文档：`docs/config_drift_checklist_v33.md`
- 默认输出目录：`docs/reports/config_drift/`
- 仅做只读检查：不修改 `.env`，不输出真实密钥值

### Phase 13.3：Governance policy summary（P1）

- 目标：
  - 汇总 rate limit、audit export redaction、OIDC、LLM opt-in、artifact/report 边界。
  - 形成 Go/No-Go 策略索引。
- 修改范围：
  - 治理策略文档与链接收口。
- 不做什么：
  - 不扩展为完整合规系统实现。
- 验证命令：
  - `python -m pytest tests/test_runtime_hardening_v055.py -q`
- 完成标准：
  - 策略边界集中可查，Go/No-Go 口径一致。

当前状态（2026-05-30）：

- 已新增脚本：`scripts/governance_policy_summary.py`
- 已新增测试：`tests/test_governance_policy_summary_v333.py`
- 已新增治理摘要文档：`docs/governance_policy_summary_v33.md`
- 默认输出目录：`docs/reports/governance_policy/`
- 仅做只读汇总与归档：不改业务逻辑，不执行真实外网 LLM

### Phase 13.4：Operations automation script polish（P1）

- 目标：
  - 统一 acceptance_snapshot / demo_e2e / failure_diagnostics 的输出路径与索引入口。
  - 保持只读优先。
- 修改范围：
  - 脚本参数与 runbook 文档（最小改动）。
- 不做什么：
  - 不新增破坏性命令，不删除历史数据。
- 验证命令：
  - `python -m pytest -q`
  - `docker compose config`
- 完成标准：
  - 产物路径一致、索引一致、无外溢副作用。

### Phase 13.5：Optional live drill window（P2）

- 目标：
  - 仅在用户明确启动服务并提供环境时执行在线演练。
- 修改范围：
  - 演练记录文档与 skipped/success 分类归档。
- 不做什么：
  - 不在默认路径执行真实外网 LLM。
- 验证命令：
  - `python -m pytest -q`
- 完成标准：
  - 条件不足时 skipped，条件满足时可追踪成功/失败证据。

### Phase 13.6：v3.3 release prep（P2）

- 目标：
  - 完成 v3.3 版本同步、release notes/review、验证矩阵与 tag 决策前复核。
- 修改范围：
  - 版本号、发布文档、readiness/runbook 口径收口。
- 不做什么：
  - 未完成复核前不打 tag、不创建 GitHub Release。
- 验证命令：
  - 以当轮全量回归（pytest / compose / frontend）为准。
- 完成标准：
  - 发布材料完整、边界准确、Go/No-Go 一致。

## 4. 推荐优先级

- **P0**：13.1 + 13.2
- **P1**：13.3 + 13.4
- **P2**：13.5 + 13.6


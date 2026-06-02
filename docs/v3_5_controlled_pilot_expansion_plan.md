# v3.5 Controlled Pilot Expansion & Evidence Operations 规划

## 定位

- v3.5 = **Controlled Pilot Expansion & Evidence Operations**。
- 核心目标：在 v3.4 已完成的操作员体验、故障演练、证据归档和交接清单基础上，继续强化受控试点扩展、证据对比、演练评分、治理例外登记和试点收口报告。
- 当前阶段仅做路线规划与入口收口，不改业务逻辑、不改版本号、不打 tag、不创建 GitHub Release。
- 当前版本保持 `3.4.0`，直到 v3.5 release prep 阶段再同步版本号。

## 基线与边界

- `v3.4.0` GitHub Release 已由用户手动创建，`v3.4.0` tag 保持不变。
- 历史 tag 保持不变：
  - `v3.3.0^{}` = `0399b84de5c2232a451d02ef37a8b181d0b01ebe`
  - `v3.2.0^{}` = `3c12985d15062328efe5711ee939ca28ba4dbacf`
  - `v3.1.0^{}` = `4ffb8044ccc0f1fb62c570308c8c9c4c8c46a99a`
  - `v3.0.0^{}` = `fa5b07b3ffb373d2f1060f38b6ef0a4d31b5194d`
- 默认路径继续保持 fake/offline，默认 pytest/CI 不调用真实外网 LLM。
- 缺少 opt-in 条件时必须记录为 `skipped`，不得伪造成成功。
- 不提交真实密钥、API key、token、client_secret、JWT_SECRET、DATABASE_URL、REDIS_URL。
- 不读取或输出真实 secret 原文。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。

## 阶段优先级

- P0：Phase 15.1、Phase 15.2。
- P1：Phase 15.3、Phase 15.4。
- P2：Phase 15.5、Phase 15.6。

## Phase 15.1：Pilot evidence comparison snapshot（P0）

### 目标

在 v3.4 evidence archive manifest 基础上，提供只读证据对比快照，帮助操作员比较两次试点证据的缺失项、过期项、状态变化和新增风险。

### 修改范围

- 新增证据对比说明文档，例如 `docs/pilot_evidence_comparison_v35.md`。
- 可选新增只读脚本 `scripts/pilot_evidence_comparison.py` 与测试。
- 默认输入来自 `docs/reports/evidence_archive/`，默认输出到 `docs/reports/pilot_evidence_comparison/`。
- 更新 `README.md`、`AGENTS.md`、`docs/production_readiness_checklist.md` 和本规划文档中的 Phase 15.1 状态。

### 不做什么

- 不读取报告正文内容。
- 不删除、移动或压缩证据文件。
- 不自动执行 retention 清理。
- 不读取或输出真实 secret 原文。
- 不执行真实外网 LLM。

### 验证命令

```powershell
python -m pytest tests/test_evidence_archive_manifest_v343.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
docker compose config
```

### 完成标准

- 能记录 baseline 与 current 两组证据索引的文件数量、缺失类型、最新文件、过期候选和状态变化。
- 空目录或缺失输入必须记录为 `skipped` 并写入 `warnings`，不得伪造成成功。
- 输出明确 `read_only=true`、`real_llm_executed=false`。
- 本阶段交付物已落地：`docs/pilot_evidence_comparison_v35.md`、`scripts/pilot_evidence_comparison.py`、`tests/test_pilot_evidence_comparison_v351.py`。

## Phase 15.2：Operator drill scoring rubric（P0）

### 目标

为故障演练、操作员交接和可选集成预检建立轻量评分口径，帮助企业内网试点复盘时判断阻塞项、可接受风险和下一步责任人。

### 修改范围

- 新增演练评分规则文档，例如 `docs/operator_drill_scoring_rubric_v35.md`。
- 可选新增只读评分脚本 `scripts/operator_drill_scoring.py` 与测试。
- 输入可引用 incident rehearsal、pilot handoff checklist、optional integration readiness 和 evidence archive manifest 产物。
- 输出默认目录为 `docs/reports/operator_drill_scoring/`。

### 不做什么

- 不自动改变 Go/No-Go 结论。
- 不把缺少 opt-in 的真实 LLM/OIDC 条件伪造成通过。
- 不执行真实外网 LLM。
- 不读取真实 secret 原文。
- 不写业务数据。

### 验证命令

```powershell
python -m pytest tests/test_incident_rehearsal_pack_v342.py tests/test_pilot_handoff_checklist_v345.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
docker compose config
```

### 完成标准

- 评分维度覆盖可用性、可恢复性、证据完整性、配置准备度、权限边界、已知限制说明。
- 评分输出必须保留原始状态词：`success / skipped / blocked / partial / failed`。
- `skipped` 必须携带缺失条件列表。
- 本阶段交付物已落地：`docs/operator_drill_scoring_rubric_v35.md`、`scripts/operator_drill_scoring.py`、`tests/test_operator_drill_scoring_v352.py`。

## Phase 15.3：Controlled integration dry-run checklist（P1）

### 目标

把真实 LLM、OIDC、外部 MCP、Postgres、Redis 等可选集成的试点前置条件整理成 dry-run checklist，用于判断是否可以安排人工受控演练。

### 修改范围

- 新增 dry-run checklist 文档，例如 `docs/controlled_integration_dry_run_v35.md`。
- 可选新增只读脚本 `scripts/controlled_integration_dry_run.py` 与测试。
- 复用 v3.4 optional integration readiness matrix 的配置存在性检查结果。
- 默认输出目录为 `docs/reports/controlled_integration_dry_run/`。

### 不做什么

- 默认不调用真实外网 LLM。
- 默认不连接真实外部 MCP。
- 不提交或打印真实密钥。
- 不默认启用 auth、RBAC、Redis 或 PostgreSQL。
- 不宣称真实集成生产验收完成。

### 验证命令

```powershell
python -m pytest tests/test_controlled_integration_dry_run_v353.py -q
python -m pytest tests/test_optional_integration_readiness_v344.py tests/test_operator_drill_scoring_v352.py tests/test_controlled_integration_dry_run_v353.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
docker compose config
```

### 完成标准

- 每个可选集成项均标记 `ready / skipped / blocked / partial`。
- 仅输出 env name 与是否存在，不输出真实值。
- 缺少 opt-in 条件时必须 `skipped`。
- 本阶段交付物已落地：`docs/controlled_integration_dry_run_v35.md`、`scripts/controlled_integration_dry_run.py`、`tests/test_controlled_integration_dry_run_v353.py`。

## Phase 15.4：Governance exception register（P1）

### 目标

建立治理例外登记模板，记录试点中允许暂时接受的风险、责任人、到期时间、补偿控制和复核证据，避免口头豁免无法追踪。

### 修改范围

- 新增治理例外登记文档，例如 `docs/governance_exception_register_v35.md`。
- 可选新增只读汇总脚本 `scripts/governance_exception_register.py` 与测试。
- 可引用 config drift、governance policy summary、incident rehearsal、operator drill scoring 的输出。
- 默认输出目录为 `docs/reports/governance_exceptions/`。

### 不做什么

- 不自动批准例外。
- 不绕过 deployment guard、安全响应头、审计脱敏或审批链路。
- 不记录真实 secret 原文。
- 不执行真实外网 LLM。

### 验证命令

```powershell
python -m pytest tests/test_governance_policy_summary_v333.py tests/test_config_drift_v332.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
docker compose config
```

### 完成标准

- 例外字段覆盖风险描述、影响范围、责任人、到期时间、补偿控制、复核证据、状态和下一步动作。
- 输出必须声明不代表生产安全豁免，也不代表公网生产可直接上线。

## Phase 15.5：Pilot closeout report pack（P2）

### 目标

形成试点收口报告包，汇总操作员工作流、故障演练、证据归档、可选集成准备度、评分和治理例外，便于管理层和实施团队做下一阶段决策。

### 修改范围

- 新增试点收口报告文档，例如 `docs/pilot_closeout_report_pack_v35.md`。
- 可选新增只读生成脚本 `scripts/pilot_closeout_report_pack.py` 与测试。
- 默认输出目录为 `docs/reports/pilot_closeout/`。
- 更新 README、AGENTS 和生产就绪清单中的 Phase 15.5 状态。

### 不做什么

- 不替代人工安全评审。
- 不自动创建 GitHub Release。
- 不改版本号。
- 不执行真实外网 LLM。
- 不宣称真实生产验收完成。

### 验证命令

```powershell
python -m pytest tests/test_pilot_handoff_checklist_v345.py tests/test_evidence_archive_manifest_v343.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
docker compose config
```

### 完成标准

- 报告包包含 executive summary、evidence summary、known limitations、Go/No-Go、next actions 和 boundary declarations。
- 对所有 skipped/blocked 项保持原始解释，不做假通过。

## Phase 15.6：v3.5 release prep（P2）

### 目标

完成 v3.5 release prep，但规划阶段不执行。release prep 才同步版本号、release notes、release review 和 tag 决策前复核。

### 修改范围

- 将版本同步到 `3.5.0`：`pyproject.toml`、FastAPI version、`/health.version`、MCP stdio fallback、脚本 version markers、相关测试断言。
- 新增 `RELEASE_NOTES_v3.5.0.md`。
- 新增 `docs/release_review_v3.5_controlled_pilot_expansion.md`。
- 更新 README、AGENTS、生产就绪清单和本规划文档。

### 不做什么

- 规划阶段不改版本号。
- 规划阶段不打 tag。
- 规划阶段不创建 GitHub Release。
- 不移动、删除或重建历史 tag。
- 不执行真实外网 LLM。

### 验证命令

```powershell
python -m pytest -q
docker compose config
npm --prefix frontend run lint
npm --prefix frontend run build
```

### 完成标准

- release notes 覆盖 Phase 15.1~15.5、状态边界与默认 fake/offline 约束。
- release review 覆盖 scope、changed docs/scripts/tests/modules、verification matrix、security/privacy boundary、operational boundary、known limitations、Go/No-Go。
- 明确可进入 tag 决策前复核，但 release prep 当轮是否打 tag 需单独确认。

## 本轮规划验收

- 已新增本规划文档。
- README、AGENTS、生产就绪清单记录 v3.5 规划入口。
- 本轮不改业务逻辑、不改版本号、不打 tag、不创建 Release。
- 本轮不执行真实外网 LLM。
- 默认 fake/offline 和默认 pytest/CI 不调用真实 LLM 边界保持不变。

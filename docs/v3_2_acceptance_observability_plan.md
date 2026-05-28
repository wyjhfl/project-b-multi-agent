# v3.2 Acceptance & Observability Enhancement 规划

## 1. 阶段定位

- v3.2 定位：**Acceptance & Observability Enhancement**。
- 目标：增强企业内网试点后的验收闭环、可观测性、演示证据归档、故障自检体验。
- 不改变既有发布事实：`v3.1.0` / `v3.0.0` tag 与对应 GitHub Release 保持不变。
- 当前版本仍为 `3.1.0`（本轮不改版本号）。

## 2. 边界声明

- 不等于公网生产直接上线。
- 不等于真实 LLM 生产验收完成。
- 不等于生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- 真实 LLM 仅 opt-in；无 opt-in 环境时必须 skipped 归档。
- 不提交密钥、token、client_secret、数据库/Redis 密码。

## 3. 建议 Phase（12.1 ~ 12.6）

### Phase 12.1：Acceptance snapshot 一键生成（P0）

- 目标：
  - 生成本地脱敏验收快照，覆盖 health / deployment / operations / metrics / audit / pilot reports / demo evidence。
- 修改范围：
  - 新增或增强 snapshot 脚本与对应文档；输出 JSON + Markdown。
- 不做什么：
  - 不触发真实 LLM，不写入密钥，不引入写操作。
- 验证命令：
  - `python -m pytest tests/test_runtime_hardening_v055.py -q`
  - `docker compose config`
  - snapshot 脚本本地执行 smoke（无服务时允许 skipped）。
- 完成标准：
  - 一条命令可生成脱敏快照；失败/跳过状态可追踪且不误报成功。

当前状态（2026-05-28）：

- 已新增脚本：`scripts/acceptance_snapshot.py`
- 已新增 runbook：`docs/acceptance_snapshot_runbook_v32.md`
- 默认输出目录：`docs/reports/acceptance_snapshots/`
- 支持输出目录覆盖参数，输出 JSON + Markdown
- 服务未启动时在线检查标记 skipped，仍可生成 offline snapshot

### Phase 12.2：前端 Observability polish（P1）

- 目标：
  - 增强 `/operations` 的空状态、错误状态、报告链接、demo evidence 展示体验。
- 修改范围：
  - 前端 `/operations` 页面与只读 API 客户端类型定义（必要时）。
- 不做什么：
  - 不新增写操作，不新增删除操作，不新增真实 LLM 调用入口。
- 验证命令：
  - `frontend npm run lint`
  - `frontend npm run build`
  - `python -m pytest tests/test_operations_summary_v312.py -q`
- 完成标准：
  - 空/错/无数据场景可读，且全部保持只读与脱敏边界。

### Phase 12.3：Demo artifact bundle（P0）

- 目标：
  - 统一 `demo_e2e` 的 artifact 输出目录，沉淀演示证据包。
- 修改范围：
  - `scripts/demo_e2e.ps1` 与 `docs/demo_e2e_runbook_v31.md`（或新增 v3.2 runbook 补充）。
- 不做什么：
  - 不依赖真实外部 MCP，不执行真实外网 LLM。
- 验证命令：
  - `powershell -ExecutionPolicy Bypass -File scripts/demo_e2e.ps1`
  - `python -m pytest tests/test_demo_seed_data_v311.py -q`
- 完成标准：
  - artifact 至少包含 seed summary、online smoke result、operations summary、pilot report index；
  - 服务未启动时明确 skipped，不误报成功。

### Phase 12.4：Failure diagnostics pack（P1）

- 目标：
  - 增强常见失败诊断输出（或文档化脚本），提升排障效率。
- 修改范围：
  - 运维排障文档与轻量只读诊断脚本（如需）。
- 不做什么：
  - 不新增破坏性清理命令，不删除用户数据。
- 验证命令：
  - `python -m pytest tests/test_deployment_guard_v60.py -q`
  - `docker compose config`
- 完成标准：
  - 覆盖 compose、deployment guard、OIDC、audit export、LLM opt-in skipped 常见路径。

### Phase 12.5：Optional real LLM evidence retry（P2）

- 目标：
  - 在用户提供 opt-in 环境变量时，补充真实 LLM 受控证据重试。
- 修改范围：
  - 执行记录文档与报告索引（不改默认路径行为）。
- 不做什么：
  - 无 opt-in 环境时不执行真实外网 LLM，不伪造成功报告。
- 验证命令：
  - `python -m pytest tests/test_real_llm_smoke_v52.py tests/test_real_llm_judge_smoke_v54.py -q`
  - `python -m pytest tests/test_llm_pilot_reports_v94.py -q`
- 完成标准：
  - success / skipped / failure 分类清晰，报告脱敏边界持续满足要求。

### Phase 12.6：v3.2 release prep（P2）

- 目标：
  - 完成 v3.2 版本同步、release notes/review、验证矩阵与 tag 决策前复核。
- 修改范围：
  - 版本号、release 文档、readiness/runbook 口径收口。
- 不做什么：
  - 未完成复核前不打 tag、不创建 GitHub Release。
- 验证命令：
  - 以当轮全量回归为准（pytest / compose / frontend）。
- 完成标准：
  - 发布材料完整、边界准确、Go/No-Go 口径一致。

## 4. 推荐优先级

- **P0**：12.1 + 12.3
- **P1**：12.2 + 12.4
- **P2**：12.5 + 12.6


Phase 12.3 current status (2026-05-28):

- `scripts/demo_e2e.ps1` enhanced with `-ArtifactDir`, default `docs/reports/demo_artifacts/`
- helper added: `scripts/demo_artifact_bundle.py`
- runbook added: `docs/demo_artifact_bundle_runbook_v32.md`
- unified artifacts: `demo_e2e_summary.json`, `online_smoke_result.json`, `seed_summary.json`, `pilot_report_index.json`, acceptance snapshot
- when service is unavailable, online smoke is marked skipped and bundle status is `completed_with_skipped_online_checks`

Phase 12.2 current status (2026-05-28):

- frontend `/operations` polished for clearer acceptance readability and operations scanability.
- explicit empty/error/skipped states added for service unavailable, no reports, no audit events, and skipped online checks.
- backend `/operations/summary` read-only metadata extended with acceptance/demo runbook paths and default artifact/snapshot directories.
- boundary maintained: read-only only, fake/offline default, no real LLM call, no secret output.

Phase 12.4 current status (2026-05-28):

- diagnostics runbook added: `docs/failure_diagnostics_pack_v32.md`
- read-only diagnostics script added: `scripts/failure_diagnostics.py`
- output: JSON + Markdown, default directory `docs/reports/failure_diagnostics/`
- covers compose / deployment guard / OIDC / audit export / demo_e2e skipped / acceptance snapshot skipped / pilot reports empty / real LLM opt-in skipped
- service unavailable is marked skipped without false success; no write/delete operation

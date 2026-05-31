# v3.4 Phase 14.1 操作员工作流收口

## 目标

Phase 14.1 聚焦操作员日常入口、runbook 链接、状态解释与只读运维证据导航。该阶段不改业务逻辑、不改版本号、不打 tag、不创建 Release。

## 只读边界

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 不执行真实外网 LLM。
- 不删除用户数据。
- 不自动清理报告。
- 不修改 `.env`。
- 不读取或输出真实 secret 原文。
- 不新增写入型运营动作。

## 日常入口

| 入口 | 什么时候用 | 默认输出目录 | 是否只读 | 是否调用真实 LLM | 失败 / skipped 解释 |
|------|------------|--------------|----------|------------------|---------------------|
| `/operations` | 日常查看 health、deployment、metrics、tasks、approvals、audit、pilot reports 与演示证据摘要 | 不写报告 | 是 | 否 | 页面或 `/operations/summary` 不可用通常表示服务未启动或后端不可达；空数据只表示暂无证据 |
| Acceptance Snapshot | 需要生成验收快照并汇总核心只读状态 | `docs/reports/acceptance_snapshots/` | 是 | 否 | 服务未启动时在线检查为 `skipped`，不伪造成成功 |
| Demo Artifact Bundle | 需要归档离线演示 seed、在线 smoke、operations summary、pilot report index 与 acceptance snapshot | `docs/reports/demo_artifacts/` | 是 | 否 | 服务不可用时 online smoke 为 `skipped` |
| Failure Diagnostics | 需要排查 compose、deployment guard、OIDC、audit export、demo/acceptance skipped、pilot reports empty、real LLM opt-in skipped | `docs/reports/failure_diagnostics/` | 是 | 否 | `blocked` 表示前置条件缺失；`partial` 表示部分在线检查不可用；`skipped` 表示缺少可选条件 |
| Report Index | 需要列出报告产物、最新文件和 stale candidates | `docs/reports/report_index/` | 是 | 否 | 空目录表示暂无报告；stale candidates 仅为候选提示，不会自动删除 |
| Config Drift | 需要检查配置模板键漂移 | `docs/reports/config_drift/` | 是 | 否 | warning 需要人工复核；脚本不自动修复 `.env` |
| Governance Summary | 需要汇总 fake/offline、真实 LLM opt-in、secret、OIDC、retention、config drift、release/tag 边界 | `docs/reports/governance_policy/` | 是 | 否 | 摘要不代表生产级安全、SSO/OIDC 或真实 LLM 生产验收完成 |
| Live Drill Window | 需要在可选真实 LLM/OIDC 演练窗口前做只读预检 | `docs/reports/live_drill_window/` | 是 | 否 | 缺少真实 LLM/OIDC opt-in 条件时必须 `skipped`；服务不可达时 `partial` |

## 统一索引脚本

```powershell
python scripts/operator_workflow_index.py --output-dir docs/reports/operator_workflow
```

脚本输出 JSON 与 Markdown，并返回统一 summary 字段：

- `status`
- `generated_at`
- `commit`
- `mode`
- `read_only`
- `real_llm_executed`
- `json_path`
- `markdown_path`
- `output_dir`

## 验证

```powershell
python -m pytest tests/test_operator_workflow_index_v341.py -q
python -m pytest tests/test_operations_automation_scripts_v334.py tests/test_runtime_hardening_v055.py -q
docker compose config
```

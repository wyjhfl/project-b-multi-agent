# v4.3.0 Release Review - Operational Governance Console Readiness

## Scope

v4.3.0 纳入 v4.0~v4.3 的生产上线评审、上线阻断项、关闭证据、人工签核、受控生产验收、验收缺口登记和运营治理台只读展示。本轮 release prep 的目标是形成 tag 前本地复核材料，不执行真实外部系统操作，不创建 tag，不创建 GitHub Release。

## Changed Files

- 版本同步：
  - `pyproject.toml`
  - `app/main.py`
  - `app/tools/mcp/stdio_client.py`
  - 相关版本断言测试
- 发布材料：
  - `RELEASE_NOTES_v4.3.0.md`
  - `docs/release_review_v4.3_operational_governance_console_readiness.md`
  - `docs/v4_3_operational_governance_console_readiness_plan.md`
- 运营治理台：
  - `app/api/operations.py`
  - `frontend/src/types/api.ts`
  - `frontend/src/app/operations/page.tsx`
  - `tests/test_operations_summary_v312.py`
- v4.0~v4.2 证据链：
  - `scripts/production_launch_readiness_review.py`
  - `scripts/launch_blocker_register.py`
  - `scripts/production_runbook_finalization.py`
  - `scripts/launch_blocker_closure_workflow.py`
  - `scripts/closure_evidence_index.py`
  - `scripts/manual_signoff_package.py`
  - `scripts/controlled_production_acceptance_drill.py`
  - `scripts/acceptance_drill_evidence_index.py`
  - `scripts/production_acceptance_gap_register.py`
  - 对应 `docs/` runbook 与 `tests/` 回归用例

## Verification Matrix

| 验证项 | 命令 | 结果 |
|---|---|---|
| 版本与 v4 证据链聚焦回归 | `D:\codex安装\tools\Python312\Scripts\pytest.exe tests/test_runtime_hardening_v055.py tests/test_operations_summary_v312.py tests/test_mcp_stdio_client_v31.py tests/test_production_launch_readiness_review_v401.py tests/test_launch_blocker_register_v402.py tests/test_production_runbook_finalization_v403.py tests/test_launch_blocker_closure_workflow_v411.py tests/test_closure_evidence_index_v412.py tests/test_manual_signoff_package_v413.py tests/test_controlled_production_acceptance_drill_v421.py tests/test_acceptance_drill_evidence_index_v422.py tests/test_production_acceptance_gap_register_v423.py` | 93 passed, 2 warnings |
| 前端 lint | `cd frontend; npm.cmd run lint` | passed |
| 前端 build | `cd frontend; npm.cmd run build` | passed |
| Diff 检查 | `git diff --check` | passed，仅 CRLF 提示 |

## Security And Privacy

- 默认 fake/offline，默认 pytest/CI 不调用真实 LLM。
- 不连接真实外部 MCP、IdP、业务系统、PostgreSQL、Redis、APM、日志平台、告警平台、KMS/Vault 或云平台。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- v4 evidence 只统计 JSON 报告数量和路径，不读取 Markdown 正文，不展开报告内容。
- 检测到 secret-like 输入、真实执行/连接标记、release/tag 标记、自动审批或自动关闭标记时，相关脚本应输出 `blocked`。

## Operational Boundary

- `metadata_available` 仅表示目录中存在 JSON 元数据，不代表验收通过。
- `skipped` 表示缺少输入或 opt-in 条件，不伪造成成功。
- `blocked` 表示边界违规、上游失败、secret-like 输入或不安全执行标记。
- `partial` 表示需要人工复核，不自动批准上线。
- `success` 仅代表本地脚本完成其有限检查，不等于生产验收完成。
- 本轮 release prep 不打 tag、不创建 GitHub Release、不移动历史 tag。

## Go/No-Go

- Go：可以进入 `v4.3.0` tag 前最终复核，并继续准备正式生产上线签核、受控真实验收和外部安全合规证据。
- No-Go：不得把本轮只读证据、`partial/success` 结果、报告计数或运营台展示当作生产上线批准。
- 公网生产直上：No-Go。

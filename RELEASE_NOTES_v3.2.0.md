# RELEASE_NOTES v3.2.0

## 版本定位

- **v3.2.0 = Acceptance & Observability Enhancement**
- 面向企业内网试点/准生产演示的验收闭环、可观测性与故障自检增强。

## Phase 12 交付摘要

- **Phase 12.1**：新增 `scripts/acceptance_snapshot.py` 与 `docs/acceptance_snapshot_runbook_v32.md`，支持本地脱敏验收快照（JSON + Markdown）。
- **Phase 12.1 cleanup**：修复快照脱敏误伤，保留 `total_prompt_tokens / total_completion_tokens / total_tokens` 等证据指标。
- **Phase 12.3**：新增 Demo artifact bundle（`scripts/demo_e2e.ps1` + `scripts/demo_artifact_bundle.py`），统一演示产物归档。
- **Phase 12.3 cleanup**：修复 `-ArtifactDir` 约束，确保本轮产物写入 artifact 目录内，避免外溢。
- **Phase 12.2**：完成 `/operations` 只读观测页 polish，与 `/operations/summary` 只读观测元数据增强。
- **Phase 12.4**：新增 failure diagnostics pack（`docs/failure_diagnostics_pack_v32.md` + `scripts/failure_diagnostics.py`）。
- **Phase 12.5**：optional real LLM evidence retry 本轮记录为 skipped（见 `docs/real_llm_optional_retry_log_v32.md`）。

## 默认行为与验证基线

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 本轮未执行真实外网 LLM。
- 本轮回归基线：**768 passed, 4 skipped**（以当轮实测为准）。

## 边界声明

- 不等于公网生产直接上线。
- 不等于真实 LLM 生产验收完成。
- 不等于生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- 不提交密钥、token、client_secret、数据库/Redis 密码明文。

## 发布状态说明

- 本文档为 **v3.2.0 release prep** 材料。
- 本轮 **不打 tag**、**不创建 GitHub Release**。

# v3.3 Phase 13.1：Report Index & Retention Runbook（只读）

## 1. 目标

- 为以下报告目录建立只读索引与保留候选列表：
  - `docs/reports/acceptance_snapshots/`
  - `docs/reports/demo_artifacts/`
  - `docs/reports/failure_diagnostics/`
- 仅输出索引与候选，不执行删除动作。

## 2. 脚本与输出

- 脚本：`scripts/report_index.py`
- 默认输出目录：`docs/reports/report_index/`
- 支持覆盖输出目录：`--output-dir`
- 输出格式：JSON + Markdown

示例：

```bash
python scripts/report_index.py
python scripts/report_index.py --output-dir .tmp_report_index_check
```

## 3. 输出字段说明

每类报告至少包含：

- `generated_at`
- `commit`
- `report_root`
- `report_type`（`acceptance_snapshot` / `demo_artifact` / `failure_diagnostics`）
- `file_count`
- `latest_generated_at`
- `latest_path`
- `total_size_bytes`
- `stale_candidates`（仅列出，不删除）
- `retention_policy`
- `boundary_declarations`

## 4. retention 策略边界

- 仅文档化与候选列表输出，不执行清理。
- 默认建议：
  - 保留最近 N 份（`keep_latest`）
  - 或保留最近 N 天（`retain_days`）
- 本阶段明确：
  - 不删除用户数据
  - 不删除报告文件
  - 不自动清理

## 5. 验证

```bash
python -m pytest tests/test_report_index_v331.py -q
python scripts/report_index.py --output-dir .tmp_report_index_check
```

确认 `.tmp_report_index_check` 下生成 JSON/Markdown 后可手动清理临时目录。

## 6. 边界声明

- 默认 fake/offline。
- 不执行真实外网 LLM。
- 不读取/输出 prompt 原文、密钥、token、client_secret、数据库/Redis 密码。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。

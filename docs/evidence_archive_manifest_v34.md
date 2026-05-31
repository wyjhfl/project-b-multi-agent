# v3.4 Phase 14.3 证据归档 Manifest

## 目标

Phase 14.3 统一列出并索引所有试点证据产物，形成只读 manifest，便于交接、审计和 release review 使用。

## 只读边界

- 不删除文件。
- 不自动执行 retention 清理。
- 不读取报告内容。
- 不读取或输出真实 secret 原文。
- 不写业务数据。
- 默认 fake/offline。
- 不执行真实外网 LLM。

## 纳入证据类型

- acceptance snapshots
- demo artifacts
- failure diagnostics
- report index outputs
- config drift outputs
- governance policy outputs
- live drill window outputs
- operator workflow outputs
- incident rehearsal outputs
- release review docs
- post release handoff docs

## 使用方式

```powershell
python scripts/evidence_archive_manifest.py --output-dir docs/reports/evidence_archive
```

## 输出字段

- `generated_at`
- `commit`
- `version`
- `manifest_id`
- `status`
- `evidence_roots`
- `evidence_items`
- `latest_by_type`
- `missing_expected_types`
- `total_files`
- `total_size_bytes`
- `retention_policy`
- `boundary_declarations`
- `read_only`
- `real_llm_executed`

## 状态解释

- `success`：所有期望证据类型均至少有一个文件。
- `warning`：存在部分证据类型缺失。
- `skipped`：当前没有任何可索引证据文件。

缺失目录或空目录不会被伪造成成功；manifest 只记录缺失类型和文件元数据。

## 验证

```powershell
python -m pytest tests/test_evidence_archive_manifest_v343.py -q
python scripts/evidence_archive_manifest.py --output-dir .tmp_evidence_manifest_check
python -m pytest tests/test_report_index_v331.py tests/test_incident_rehearsal_pack_v342.py -q
docker compose config
```

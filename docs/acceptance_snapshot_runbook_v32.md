# v3.2 Phase 12.1：Acceptance Snapshot Runbook

## 1. 目标

- 一键生成本地脱敏验收快照（JSON + Markdown）。
- 用于企业内网试点验收归档，不用于公网生产上线审批。

## 2. 执行命令

```bash
python scripts/acceptance_snapshot.py
```

可选参数：

```bash
python scripts/acceptance_snapshot.py --output-dir docs/reports/acceptance_snapshots --base-url http://localhost:8000
```

## 3. 默认输出

- 默认目录：`docs/reports/acceptance_snapshots/`
- 输出文件：
  - `<timestamp>_<commit>_acceptance_snapshot.json`
  - `<timestamp>_<commit>_acceptance_snapshot.md`

## 4. 快照覆盖字段

- generated_at
- commit
- version
- environment/mode
- health 摘要
- deployment check 摘要
- operations summary 摘要
- runtime metrics 摘要
- audit 最近事件脱敏摘要
- pilot reports 索引
- demo evidence 路径
- skipped / limitations / boundary 声明

## 5. 脱敏与边界

- 不包含 prompt/query/raw_prompt/sql_prompt 原文。
- 不包含 API key/token/client_secret/password/JWT_SECRET/DATABASE_URL/REDIS_URL 明文。
- DSN 密码按脱敏规则处理。
- 默认 fake/offline，不触发真实 LLM，不写业务数据。

## 6. 服务未启动场景

- 脚本会优先尝试在线检查（`/health`、`/deployment/check`、`/operations/summary`）。
- 若服务未启动，在线检查标记为 `skipped`，并生成 offline snapshot。
- 不会误报“全部成功”。

## 7. 验证建议

```bash
python -m pytest tests/test_acceptance_snapshot_v321.py -q
python -m pytest tests/test_runtime_hardening_v055.py -q
docker compose config
```

## 8. 边界声明

- not public production approval
- not real LLM production acceptance
- no raw prompt / no secrets

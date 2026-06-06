# v4.1 Launch Blocker Closure Workflow（只读）

## 定位

本阶段将 v4.0 Launch Blocker Register 转成可人工复核的关闭工作流。它只判断阻断项是否具备进入人工复核的证据，不自动批准上线，不自动关闭 blocker，也不把 `skipped`、`partial` 或本地证据汇总包装成生产 Go。

## 输入与输出

- 输入：v4.0 `launch_blocker_register.py` 生成的 JSON。
- 可选输入：脱敏后的 closure evidence JSON，字段建议包含 `source_key` 或 `blocker_id`、`owner`、`due_at`、`compensating_controls`、`closure_evidence_refs`、`reviewer`、`approval_state`。
- 输出目录：`docs/reports/launch_blocker_closure/`。
- 输出格式：JSON + Markdown。

## 状态语义

- `skipped`：未提供 launch blocker register、输入不可读取、或上游 blocker register 保持 skipped。
- `partial`：存在 open blocker，但关闭证据缺失或不完整。
- `blocked`：上游 blocked/failed、检测到 secret-like 输入、发现真实执行标记、审批拒绝或违反只读边界。
- `success`：当前阶段不主动使用，避免把流程完整性误读为生产 Go。

所有 blocker 均具备 owner、due_at、补偿控制、证据引用、reviewer 与 `pending_review/approved` 状态时，整体仍输出 `partial`，语义为 closure package 可进入人工复核，不表示 blocker 已关闭，不表示生产 Go。

## 只读边界

- 不读取 Markdown 报告正文。
- 不修改上游报告、`.env` 或环境变量。
- 不写业务、审计或指标数据。
- 不读取或输出真实 secret、token、API key、client_secret、连接串密码或 webhook 原文。
- 不执行真实 LLM、真实 MCP、真实 IdP、真实业务系统、数据库、Redis、APM、日志、告警、KMS、Vault、对象存储或云平台连接。
- 不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、红队测试、审计导出、密钥轮换或权限变更。
- 不自动批准上线，不自动关闭 blocker，不打 tag，不创建 GitHub Release。

## 验收命令

```powershell
python -m pytest tests/test_launch_blocker_closure_workflow_v411.py
```

后续进入 v4.2 前，应将本工作流与 v4.0 Phase 20.1/20.2/20.3/20.4 的最小测试一起回归。

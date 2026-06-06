# v4.0 Phase 20.2 Launch Blocker Register Runbook

## 目标

本 runbook 用于生成生产上线阻断项登记册，把 v4.0 Launch Readiness Review 输出中的 production blockers 和 missing conditions 整理为可人工跟踪的台账。

登记册用于记录阻断项描述、影响范围、责任人、到期时间、补偿控制、关闭证据和下一步动作。它不自动批准上线，不自动关闭阻断项，不替代安全、合规、SRE、发布门禁或管理层签核。

## 默认命令

```powershell
python scripts/launch_blocker_register.py
```

默认输出目录：

```text
docs/reports/launch_blockers/
```

推荐从 Phase 20.1 评审 JSON 生成：

```powershell
python scripts/launch_blocker_register.py `
  --launch-readiness docs/reports/production_launch_readiness/<review>.json `
  --output-dir docs/reports/launch_blockers
```

## 状态语义

### 顶层状态

- `success`：保留给未来“所有 blocker 已由人工关闭且关闭证据可验证”的扩展场景；当前默认生成逻辑不自动输出 `success`，避免把未关闭阻断项伪造成生产 Go。
- `partial`：存在待关闭阻断项，或者输入证据仍需人工补齐。
- `skipped`：未提供 Launch Readiness 输入，或输入不可加载；必须保留缺失条件。
- `blocked`：发现 secret-like 输入、非只读输入、意外真实外部执行、上游 `blocked/failed` 或自动批准/关闭风险。
- `failed`：脚本执行异常或输出不可用。

### 阻断项状态

- `open`：需要人工关闭。
- `blocked`：存在 secret、边界违规或上游阻断状态，必须先处理。
- `skipped`：缺少上游输入或上游状态为 `skipped`，无法登记为 open。
- `closed`：仅允许后续人工流程基于关闭证据设置；脚本默认不生成 closed。

## 字段

每条 blocker 至少包含：

- `blocker_id`
- `source`
- `risk_description`
- `scope`
- `owner`
- `due_at`
- `compensating_controls`
- `closure_evidence`
- `status`
- `approval_state`
- `next_actions`

默认 `owner=manual_owner_required`，`due_at=manual_due_date_required`，`approval_state=not_approved`。

## 只读边界

- 默认 fake/offline。
- 不启动服务，不访问在线端点。
- 不连接真实 IdP、LLM provider、外部 MCP、业务系统、PostgreSQL、Redis、APM、日志、告警、KMS、Vault、对象存储或云平台。
- 不读取 `.env` 或真实 secret 值。
- 不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、红队测试、审计导出、密钥轮换或权限变更。
- 不写业务数据，不修改上游报告，不移动、删除、重建历史 tag。
- 不自动批准上线，不自动关闭阻断项，不创建 GitHub Release。
- 不把 `skipped/blocked/partial` 或未关闭 blocker 伪造成生产 Go。

## Secret 边界

- 禁止输出 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文。
- 如果输入中出现疑似 secret，输出必须标记为 `blocked` 并仅保留脱敏后的风险说明。

## Go/No-Go 口径

- 公网生产直上：No-Go。
- 企业内网受控试点评审：可继续人工复核，但所有 blocker 必须有责任人、到期时间、补偿控制和关闭证据。
- 最终生产 Go：必须由人工签核，脚本不能自动批准。

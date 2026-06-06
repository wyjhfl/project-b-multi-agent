# v4.1 人工签核包（只读）

## 定位

`scripts/manual_signoff_package.py` 用于生成人工复核材料，并校验结构化人工签核记录 JSON。它只读取结构化 JSON 字段，不自动签核、不自动批准上线、不自动关闭 blocker。

## 生成签核记录模板

```powershell
python scripts/manual_signoff_package.py --write-template docs/reports/manual_signoff_package/manual_signoff_record.template.json
```

模板默认是 `No-Go`、`manual_signoff_completed=false`，四个角色和四个证据确认项均未批准。填写时不要写入 token、API key、数据库连接串或客户敏感数据。

## 必填角色

- `release_manager`：确认发布窗口、回滚方案、变更审批和版本范围。
- `security_reviewer`：确认密钥不泄漏、权限边界、审计证据和安全复核结论。
- `business_owner`：确认业务只读/写入边界、试点范围和残余风险接受。
- `operations_owner`：确认监控、备份恢复、值守和故障处置准备。

## 必填证据确认项

- `real_llm_preflight`：小米真实 LLM 预检报告为 `success`，且未输出 API key 原文。
- `postgres_redis_mcp_smoke`：PostgreSQL、Redis、external MCP 当前轮 smoke 证据已通过。
- `business_read_smoke`：业务系统只读 smoke 已通过，且未执行写入。
- `closure_evidence_review`：launch blocker closure evidence 已进入人工复核状态。

只有四个角色全部 `approved=true`、四个证据确认项全部 `accepted=true`，且 `decision=Go`、`manual_signoff_completed=true`、`public_production_direct_launch=No-Go` 时，签核记录才会被视为完成。

## 生成签核包

```powershell
python scripts/manual_signoff_package.py --closure-index <closure-index.json> --signoff-record <manual-signoff-record.json>
```

如果没有 `closure-index.json` 或人工签核记录，脚本会保持 `skipped/partial`，不会伪造成已完成。

## 边界

- 不读取 Markdown 正文。
- 不读取或输出真实 secret 原文。
- 不修改、不移动、不删除输入证据。
- 不执行真实部署、迁移、发布、回滚、压测、备份恢复、安全扫描、审计导出、密钥轮换或权限变更。
- `public_production_direct_launch` 必须保持 `No-Go`。

## 验收命令

```powershell
pytest tests/test_manual_signoff_package_v413.py
```

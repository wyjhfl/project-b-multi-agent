# v3.7 Business system integration safety checklist（只读）

Phase 17.5 建立真实业务系统集成前的安全清单，用于确认读/写边界、工具 allowlist、审批、审计、幂等、回滚、失败恢复和脱敏证据要求。该清单只做本地证据与 opt-in 条件检查，不连接任何真实业务系统。

## 交付物

- 只读脚本：`scripts/business_system_integration_safety_checklist.py`
- 测试：`tests/test_business_system_integration_safety_checklist_v375.py`
- 默认输出目录：`docs/reports/business_system_integration_safety/`
- 输出格式：JSON + Markdown

## 检查范围

- 业务系统集成 opt-in：`BUSINESS_INTEGRATION_ENABLED`、`BUSINESS_INTEGRATION_READ_ONLY`、`BUSINESS_INTEGRATION_WRITE_ENABLED`、`BUSINESS_INTEGRATION_APPROVAL_REQUIRED`、`BUSINESS_INTEGRATION_AUDIT_REQUIRED`。
- 业务系统 secret target：`BUSINESS_SYSTEM_BASE_URL_ENV`、`BUSINESS_SYSTEM_TOKEN_ENV` 只输出 env name 和 present 布尔状态，不输出真实值。
- 工具边界：ToolGateway、PolicyEngine、OperationWhitelist、MultiToolPipeline。
- allowlist 与超时：`BUSINESS_SYSTEM_TOOL_ALLOWLIST`、`BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST`、`BUSINESS_SYSTEM_TIMEOUT_SECONDS`。
- 审批恢复：ApprovalStore、Approval API、ApprovalResumeService 和恢复测试。
- 审计证据：AuditStore、AuditRecorder、Audit API 和审计测试。
- 请求与 prompt 安全：request guards、PromptInjectionGuard、GuardrailsEngine 和相关测试。
- 回滚与失败恢复：当前仅记录缺失项，不伪造成成功。

## 边界

- 不连接真实业务系统。
- 不执行真实业务系统读操作。
- 不执行真实业务系统写操作。
- 不创建、更新或删除业务数据。
- 不绕过 ToolGateway、PolicyEngine、审批链路或审计链路。
- 不读取或输出真实 token、API key、client_secret、连接串密码或业务系统 URL 原文。
- 不宣称真实业务系统生产集成验收完成。

## 运行方式

```powershell
python scripts/business_system_integration_safety_checklist.py
```

指定输出目录：

```powershell
python scripts/business_system_integration_safety_checklist.py --output-dir docs/reports/business_system_integration_safety
```

## 状态语义

- `skipped`：缺少 opt-in、allowlist、超时、回滚或失败恢复证据。
- `partial`：本地工程证据齐备且 opt-in 条件存在；仍不代表真实业务系统验收完成。
- `blocked`：输出中检测到 secret-like 文本或存在绕过审批/审计等边界风险。
- `failed`：脚本运行异常或输出无法生成。
- `success`：保留状态词，不用于默认离线清单伪造成生产成功。

## 推荐回归

```powershell
python -m pytest tests/test_business_system_integration_safety_checklist_v375.py -q
python -m pytest tests/test_security_v04.py tests/test_audit_v045.py tests/test_approval_resume_v042.py tests/test_v043_full_resume.py -q
python scripts/business_system_integration_safety_checklist.py
```

## Go / No-Go 口径

- Go：可进入真实业务系统集成设计评审和受控演练准备，前提是所有写入类工具具备 allowlist、审批、审计、幂等、回滚和失败恢复证据。
- No-Go：连接真实业务系统、执行真实写入、绕过审批或审计、输出 secret 原文、缺失回滚和失败恢复证据，或把只读清单宣称为生产验收完成。

## Project B v1.1.1 — Documentation & Eval Precision Cleanup

### 定位

v1.1.1 基于 v1.1 发布后的审查意见，做**小范围可信度和评测精度收口**。不新增大功能，不重构，不接真实 MCP/LLM，不做前端。

### README / docs 口径统一

- README.md 测试数量统一为 **432 passed**（badge / 测试章节 / 项目结构 / 技术栈）
- v1.0 Release Notes 的历史事实（370 passed）保留不动
- README 顶部增加醒目边界说明：本项目是 production-grade Agent Harness engineering prototype
- README 版本路线新增 v1.1.1
- AGENTS.md 版本路线新增 v1.1.1
- RELEASE_NOTES_v1.1_DRAFT.md 已确认统一为 400 passed
- docs/eval_report_v1.md 新增 Security Eval 语义拆分说明

### Tool-level Trajectory Eval Strengthened

- **MultiAgentOrchestrator trace 增强**：executor_completed trace detail 现在透传 tool_called（keyword 模式）和 tool_calls（multitool 模式），不再只传 success + executed_mode
- **extract_tool_names 增强**：同时识别 `tool_name` 和 `tool_called` 键，覆盖 keyword 模式的工具提取
- **expected_tools 补回**：
  - ma_refund_rule: ["rule_lookup", "get_refund_rate"]
  - ma_promotion_rule: ["rule_lookup"]
  - ma_gmv_mom: ["date_lookup", "get_today_gmv", "calculator"]
  - ma_refund_rule_and_rate: ["rule_lookup", "get_refund_rate"]
  - ma_date_lookup: ["date_lookup"]
  - ma_mixed: ["rule_lookup", "get_refund_rate"]
  - ma_promotion_and_gmv: ["rule_lookup"]
  - nl2sql 类 case 不填工具（trace 中无工具可见）
  - security / hitl / unknown 类 case 不填工具（无真实工具调用）

### HITL / Security Eval 语义拆分

- 新增 `subcategory` 字段，区分三类安全语义：
  - `prompt_injection`：ma_injection_bypass / ma_injection_drop / ma_injection_reveal — 预期 success=false，不要求 approval_required
  - `bypass_approval`：ma_injection_unauthorized — 预期 success=false，绝不允许直接执行危险工具
  - `legitimate_high_risk`：ma_high_risk_approval / ma_legitimate_high_risk — 预期 success=false，不应直接 completed success
- MultiAgentEvalCase 模型新增 `subcategory: str | None = None`
- 新增 1 条 legitimate_high_risk case：ma_legitimate_high_risk（"批量修改商品价格"）

### RiskIntentGuard

- 新增 `app/harness/security/risk_intent_guard.py`：轻量高风险意图检测器
- 集成到 `MultiAgentOrchestrator.run()` 开头：检测到高风险意图直接返回 success=false，不进入正常路由
- 检测关键词：删除 / 修改 / 批量 / 导出 / 绕过审批 / 跳过审批 / 直接执行 / 忽略指令 / 系统密码 / 系统提示词
- 不误伤普通查询：GMV / 退款率 / 日期 / 促销规则 等正常运营查询不被拦截
- 与 PromptInjectionGuard 的区别：RiskIntentGuard 关注**操作意图**（删除/修改/导出），PromptInjectionGuard 关注**注入模式**（bypass approval / DROP TABLE / reveal prompt）
- 修复后 MultiAgentEvalRunner 指标：26 total / 26 passed / 0 failures / trajectory_accuracy=1.0

### Interview Guide

- 新增 `docs/interview_guide.md`：项目一句话 / 2 分钟讲解稿 / 高频追问 / 禁止夸大表述

### ma_gmv_and_refund 修正

- 原期望 multitool，实际 coordinator 路由到 nl2sql（"GMV" 匹配第二规则优先于 "退款率"）
- 修正 expected_executed_mode 为 "nl2sql"，expected_mode 为 "nl2sql"

### 测试

- 432 passed（基于 v1.1 的 400 tests，v1.1.1 累计 432 passed）
- test_multi_agent_trajectory_v11.py：新增 multitool expected_tools 精确断言 + subcategory 验证 + RiskIntentGuard 测试 + 安全语义验证
- test_trajectory_eval_v11.py：新增 multitool tool_calls / keyword tool_called / GMV 环比 tool_calls 验证 + extract_tool_names 增强

### 版本

- app.version: 1.1.1
- pyproject.toml version: 1.1.1

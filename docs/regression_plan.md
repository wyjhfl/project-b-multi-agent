# v0.5 回归集组织

## 分层回归

| 版本 | 功能 | 测试文件 | 覆盖范围 |
|------|------|---------|---------|
| v0.1 | keyword 查询 | test_project_bootstrap.py | 基础 keyword 模式、TaskRun、ToolGateway |
| v0.2 | NL2SQL | test_nl2sql_v02.py | SQL 生成、SQLGuard、Preview/Execute |
| v0.3 | MultiTool / MultiAgent | test_multitool_v03.py, test_multi_agent_v03.py, test_mcp_gateway_v03.py | 多工具编排、四角色协调、MCP fake |
| v0.3 | Trace / Eval | test_observability_eval_v03.py | TraceRecorder、12 case 回归集、BadCase |
| v0.3 | Docker / Config | test_v03_closure_mcp_docker.py | Docker Compose、MCP 配置 |
| v0.3 | Persistence | test_v036_persistence_eval.py | SQLiteTaskStore、fallback trace |
| v0.4 | HITL Approval | test_hitl_v04.py, test_approval_resume_v042.py, test_v043_full_resume.py | 审批创建/决策/幂等、keyword/multitool resume |
| v0.4 | Security | test_security_v04.py | PromptInjectionGuard、OperationWhitelist、payload tampered |
| v0.4 | Audit | test_audit_v045.py | SQLiteAuditStore、AuditRecorder、audit API |
| v0.5 | Runtime Hardening | test_runtime_v05.py | audit path cleanup、UTC timestamp、time range query、metrics |
| v0.5 | BadCase + Judge | test_badcase_eval_v05.py | 30+ bad case 回归、FakeJudge、BadCaseRunner、Eval API |
| v0.5 | Memory / Skills / Reflection | test_runtime_memory_skills_reflection_v05.py | ShortTermMemory、SkillRegistry、SelfCheckEngine、API |
| v0.5 | Runtime Persistence + Cost Dashboard | test_runtime_persistence_v05.py | SQLiteMetricsStore、双写、Cost/Tools/Tasks API、Snapshot、Reflection 语义、session_id |
| v0.5 | Runtime Hardening 收口 | test_runtime_hardening_v055.py | by_mode 归因、tool task_id、Memory.summary、Snapshot 容错、版本号 |

## BadCase 数据集

30 个 case，按 suite 分层：

| Suite | 数量 | 覆盖 | 真实化程度 |
|-------|------|------|-----------|
| security | 8 | prompt injection（中英文绕过、reveal system prompt、DROP/DELETE） | 真实 PromptInjectionGuard |
| nl2sql | 6 | unmatched、GMV、dangerous SQL、empty query、top products、refund rate | 真实 SQLGuard + NL2SQLPipeline |
| multitool | 5 | unmatched、unknown tool、high risk approval、multi step | 真实 MultiToolPipeline |
| approval | 5 | pending/rejected resume、payload tampered、retry、new approval | **部分真实化**：pending/rejected/tampered 使用真实 ApprovalResumeService |
| multi_agent | 4 | unknown query、vague query、mixed query、mode confusion | 真实 MultiAgentOrchestrator |
| runtime | 2 | audit empty result、metrics zero state | 真实 AuditStore / MetricsRecorder |

数据文件：`data/evaluation/bad_cases.json`

## LLM-as-Judge 评测骨架

当前使用 FakeJudge（规则型打分）：
- expected == actual → score 1.0
- error_type 命中 → score 1.0
- blocked-like → score 0.8
- 其他 mismatch → score 0.0

LLMJudgeProvider 提供可选真实 provider 路径：默认仍使用 FakeJudge 与离线回归路径，不在默认测试中调用真实 LLM。

真实 LLM Judge 后移，不在本阶段。

## ShortTermMemory

- 内存实现，不持久化
- add_message / get_messages / summarize / clear / get_context
- AgentKernel 执行时自动写入 user query + assistant result
- API: GET /memory/{session_id}, DELETE /memory/{session_id}
- 注意：这是短期上下文，不是长期记忆

## SkillRegistry

- 4 个内置 Skills：ops_metrics / product_analysis / policy_lookup / nl2sql_analysis
- 规则型 trigger 匹配
- API: GET /skills, POST /skills/match
- 注意：这是规则型技能注册与匹配，不是独立 Agent

## SelfCheckEngine

规则型自检，8 项检查：
- result_success / approval_consistency / injection_consistency / tool_call_consistency
- nl2sql_consistency / audit_consistency / empty_result / waiting_approval
- API: POST /reflection/check
- 注意：这是规则型自检，不是 LLM 反思
- v0.5 第四阶段修正：empty_answer → empty_result，_has_presentable_result 多字段检查，waiting_approval 不被 result_success 误判

## 如何运行

```bash
# 运行 BadCase 评测
curl -X POST http://localhost:8000/eval/bad-cases/run -H "Content-Type: application/json" -d '{"use_judge": false}'

# 运行带 Judge 的 BadCase 评测
curl -X POST http://localhost:8000/eval/bad-cases/run -H "Content-Type: application/json" -d '{"use_judge": true}'

# 查看 BadCase 列表
curl http://localhost:8000/eval/bad-cases
curl http://localhost:8000/eval/bad-cases?suite=security

# 查看 Eval Summary（含 bad_case_count）
curl http://localhost:8000/eval/summary

# 查看短期记忆
curl http://localhost:8000/memory/{session_id}

# 查看技能列表
curl http://localhost:8000/skills

# 匹配技能
curl -X POST http://localhost:8000/skills/match -H "Content-Type: application/json" -d '{"query": "今日GMV"}'

# 执行 Reflection 自检
curl -X POST http://localhost:8000/reflection/check -H "Content-Type: application/json" -d '{"task_result": {"success": true, "answer": "GMV is 10000"}}'
```

## 当前测试数

370 个测试（v0.5 第五阶段结束时）

## v0.5 第五阶段新增

### cost_summary by_mode 归因修复

- 不再使用 GROUP BY task_id HAVING MIN(rowid)
- Python 侧构建 task_mode_map：每个 task_id 取最早一条 task metric 的 mode

### tool metrics task_id 归因

- RuntimeMetricsRecorder.record_tool_call 增加可选 task_id 参数
- ToolGateway.call 增加可选 task_id 参数
- ToolGateway.set_current_task_id() 方法
- AgentKernel._execute 传入 task_id

### ShortTermMemory.summary()

- 返回 session_count / message_count / sessions
- runtime_snapshot.py 不再访问 _sessions 私有字段

### Runtime Snapshot 容错

- _safe_section 包裹每个 section
- 任一 section 异常返回 {"error": "..."} 而非整体 500

### 版本号

- app.version 更新为 0.5.5

## v0.5 第四阶段新增

### SQLiteMetricsStore

- 三张 append-only 表：runtime_task_metrics / runtime_tool_metrics / runtime_token_usage
- 查询方法：summary() / task_summary() / tool_summary() / cost_summary()
- 支持 start_time / end_time 过滤
- limit 边界：≤0 默认 100，>500 截断 500
- db_path dirname 为空时不调用 os.makedirs

### RuntimeMetricsRecorder 双写

- 支持可选 metrics_store（SQLiteMetricsStore）
- record_task / record_tool_call / record_token_usage 写内存的同时 append 到 SQLite
- SQLite 写入失败时只 log warning，不影响主流程
- 保持 /metrics/runtime 原有字段兼容

### Cost Dashboard 数据 API

| API | 说明 |
|-----|------|
| GET /metrics/runtime | 原有内存 metrics（兼容） |
| GET /metrics/cost/summary | 成本汇总：total_prompt_tokens / total_completion_tokens / total_cost / by_mode / by_day |
| GET /metrics/tools/summary | 工具汇总：tool_call_count / tool_failure_count / retry_count / avg_latency_ms / by_tool |
| GET /metrics/tasks/summary | 任务汇总：task_count / success_count / failed_count / waiting_approval_count / cancelled_count / unknown_status_count / avg_task_latency_ms / by_mode |

当前没有真实 LLM token/cost 时返回 0，但字段稳定。Cost Dashboard 目前是 API 数据准备，不做前端。

### Runtime Snapshot API

| API | 说明 |
|-----|------|
| GET /runtime/snapshot | 运行时快照 |

返回：app_version / metrics_summary / cost_summary / task_summary / tool_summary / audit_summary / memory_summary / skills_summary

本阶段只做导出，不做 restore/import。

### Memory session_id 支持

- CreateTaskRequest 增加可选 session_id
- 同一 session_id 下多次任务共享 ShortTermMemory
- 不传 session_id 时旧行为不变

### SkillRegistry 全局化

- main.py 创建全局 SkillRegistry，get_skill_registry() 返回同一实例
- skills_api.py 使用全局实例，不再每次临时创建

## 后续扩展计划

- v0.5 第四阶段：Runtime Persistence + Cost Dashboard Prep ✅
- v0.5 第五阶段：待规划
- v0.6+：真实 MCP stdio 协议、真实 LLM Judge、50+ bad case

## 本阶段不实现

- 真实 LLM Judge / LLM Reflection
- 真实 MCP Server
- 前端 UI
- 长期记忆 / 向量库
- 持久化 Skill Learning
- Runtime Snapshot restore/import
- 真实 LLM 成本统计（需 provider 接入后完善）

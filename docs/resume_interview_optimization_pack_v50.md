# Project B 简历与面试优化包 v5.0

## 简历项目定位

Project B 是一个面向企业运营场景的生产级 Agent Runtime 工程化原型。项目重点不是做一个聊天 Demo，而是把 Agent 执行所需的安全、审批、审计、评测、可观测、成本、工具网关和受控试点证据链做成可运行的工程系统。

当前推荐简历定位：

> 设计并实现生产级 Agent Runtime 工程化原型，基于 FastAPI、LangGraph Adapter、Tool Gateway、PolicyEngine、HITL 审批、审计追踪、Eval 回归与运营台，支持 keyword、NL2SQL、multi-tool 和确定性 multi-role orchestration 等模式，并提供受控内网试点落地证据链。项目默认 fake/offline，可选接入真实 LLM、PostgreSQL、Redis、MCP，但不宣称公网生产可直接上线。

边界必须说清楚：

- 当前是生产级工程化原型与受控内网试点，不是已完成公网生产验收的 SaaS。
- 真实业务系统暂未接入，当前通过 demo read-only business interface 保持可演示路径。
- public_production_direct_launch=No-Go，真实业务系统、真实 IdP、多租户和公网安全验收完成前不开放公网直上。
- Multi-Agent 是确定性多角色编排，不包装成完全自治 Agent。

## 2 分钟项目讲解

这个项目解决的是 Agent 从 Demo 到企业试点之间的工程化断层。大多数 Demo 只展示 LLM 调工具，但真实企业系统更关心三件事：能否控制风险、能否审计追溯、能否稳定验收。

我把系统拆成 Harness Runtime 和业务能力两层。Harness Runtime 负责上下文组装、策略拦截、工具网关、审批恢复、追踪审计和指标记录；业务能力包括 NL2SQL、multi-tool pipeline、确定性 multi-role orchestration、运营台和真实集成预检。高风险操作会被 PolicyEngine 拦截并进入 HITL 审批，审批后通过 resume 机制恢复执行，避免直接裸调 LLM 造成不可控写入。

为了让项目可落地，我还做了受控试点证据链：real integration readiness、staging smoke、business read smoke、controlled pilot run packet、evidence freshness、text quality guard、signoff closeout 等脚本都会输出结构化 JSON/Markdown 报告。Operations Command Center 作为面试和演示入口，会把当前 controlled pilot、public launch、precommit、action pack、Operator Guidance 等状态聚合到只读运营台。

当前没有真实业务系统时，项目仍然可以通过 demo read-only path 完整展示架构、安全边界和落地流程；但公网生产仍保持 No-Go，这也是面试时应主动说明的工程边界。

## 简历亮点写法

### 一句话版本

生产级 Agent Runtime 工程化原型：围绕 Tool Gateway、PolicyEngine、HITL 审批恢复、审计追踪、Eval 回归、运营台和受控试点证据链，构建可演示、可审查、可扩展的企业 Agent 落地框架。

### 技术亮点版本

- 设计五层 Harness Runtime，将上下文组装、策略拦截、工具调用、追踪审计和指标采集解耦，避免业务 Agent 裸调 LLM。
- 实现 Tool Gateway 统一管理 local tools 与 MCP tools，并通过 allowlist、PolicyEngine 和审计链路约束真实工具调用。
- 实现 HITL 审批与 resume 链路，高风险操作进入审批，审批后恢复执行并记录 trace/audit，支持幂等边界。
- 实现 NL2SQL 安全链路，包含 schema metadata、SQLGuard、只读执行器、结果格式化和图表规划。
- 建立 Eval/BadCase 回归体系，默认 fake/offline，不依赖真实 LLM 也能验证安全、审批、工具和运行时行为。
- 建立受控内网试点证据链，输出 JSON/Markdown 报告并在 Operations Command Center 聚合展示。

## 可演示路径

### 0. 面试演示就绪自检

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\interview_demo_readiness.py
```

用途：面试前确认简历材料、Operations Command Center、Operator Guidance、受控 demo 脚本和 No-Go 边界都可被结构化证明。

### 1. 受控 demo 落地链路

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\controlled_pilot_demo_landing.ps1 -EnvPath local\production_landing.staging.env
```

用途：在没有真实业务系统时，执行 demo read-only 受控试点链路，生成 run packet、evidence archive、text quality 等证据。

预期口径：

- controlled_internal_pilot 可能是 Go 或 Manual-Review，取决于证据新鲜度与当前工作区状态。
- public_production_direct_launch 必须始终是 No-Go。
- 不写真实业务数据，不输出 secret 原文。

### 2. 运营台演示入口

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\controlled_pilot_console_up.ps1 -BackendPort 8000 -FrontendPort 3004
```

打开：

```text
http://127.0.0.1:3004/operations
```

重点展示：

- Landing Command Center
- Evidence Chain
- Next Actions
- Review Reasons
- Operator Guidance
- public_production_direct_launch=No-Go

### 3. 文本质量与边界检查

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\production_landing_text_quality_check.py
```

用途：扫描落地文档、脚本、简历面试材料，防止乱码、坏字符串、secret-like 明文进入仓库。

## 面试高频追问

### Q1：为什么你说这是生产级工程化，而不是普通 Agent Demo？

普通 Demo 关注模型回答是否看起来聪明。这个项目关注企业落地时必须具备的横切能力：工具调用是否可控，危险操作是否审批，执行过程是否可追踪，审计是否可导出，成本和 token 是否可观测，回归测试是否能证明安全边界没有退化。这些能力不依赖单个 prompt，而是落在 Runtime、Gateway、Policy、Audit、Eval 和 Operations Console 上。

### Q2：没有真实业务系统，为什么还能写进简历？

可以写，但必须准确表达。当前项目已经实现业务系统接入前的安全准备、只读 smoke 模板、demo read-only interface、受控试点证据链和公网 No-Go 边界。它证明的是我能设计企业级 Agent 落地框架和集成门禁，不证明我已经完成某个真实企业业务系统的生产验收。

### Q3：面试官问“真实 LLM/MCP/PostgreSQL/Redis 是否接入完成”怎么回答？

回答要分层：

- 默认路径 fake/offline，保证本地和 CI 稳定。
- 真实 LLM、PostgreSQL、Redis、MCP 都有 opt-in 配置、preflight、smoke 或 readiness 证据脚本。
- 已经做过受控接入验证的部分可以展示对应报告，但不把 opt-in smoke 包装成生产验收完成。
- 没有真实业务系统前，公网生产直上保持 No-Go。

### Q4：这个项目最大的工程难点是什么？

最大难点不是接一个模型，而是把“不确定的 LLM 行为”放进确定性的工程边界里。具体包括：工具网关统一入口、策略和白名单分层、HITL 审批恢复、审计脱敏、Eval 防虚假通过、证据新鲜度检查、Windows 环境编码和 Python 运行时兼容。这些都是 Demo 项目通常不处理，但企业试点必须处理的问题。

### Q5：如果继续做生产化，你下一步会做什么？

优先级如下：

1. 保持无真实业务系统路径可演示，把 Operations Command Center 打磨成面试主入口。
2. 准备真实业务系统只读接口规范，一旦用户有系统即可执行 read-only smoke。
3. 建立一键 demo seed、console up、browser verify、evidence freshness 的面试演示脚本。
4. 收敛 README 与简历材料，避免版本跨度太大导致面试口径混乱。
5. 在真实业务系统、真实 IdP 和安全验收完成前，继续保持公网生产 No-Go。

## 后续优化规划

### P0：面试演示闭环

- 强化 Operations Command Center 顶部决策视图。
- 将 Operator Guidance 暴露为可复制的只读命令清单。
- 让 Review Reasons 直接解释 Manual-Review 的原因。
- 运行 `scripts\interview_demo_readiness.py` 生成面试自检报告。
- 验证方式：pytest focused suite、前端 build、浏览器 smoke。

### P1：简历材料收口

- 保留 `docs/resume_blog_notes.md` 作为长文素材。
- 保留 `docs/interview_guide.md` 作为问答素材。
- 使用本文档作为当前版本的面试主材料。
- 验证方式：文本质量 guard 纳入三份材料。

### P2：真实系统接入前准备

- 不接入虚构业务系统。
- 保留业务系统只读接口准备清单。
- 后续有真实系统后，先执行 read-only smoke，再进入 controlled pilot。
- 验证方式：business_system_read_smoke 与 readiness brief 生成脱敏报告。

### P3：最终提交前收口

- 统一运行 focused backend tests、frontend lint/build、text quality、browser smoke。
- 清理缓存与临时服务。
- 最后再做一次证据新鲜度刷新、总结、提交和推送。

# AGENTS.md — 仓库级规则

## 语言

- 所有文档和注释使用**简体中文**

## 安全

- **禁止提交任何密钥、Token、API Key** 到仓库
- 敏感配置通过 `.env` 文件管理，`.env` 已在 `.gitignore` 中排除
- 使用 `.env.example` 提供配置模板

## 版本范围

- **v0.1 只做 Harness Core**，不提前实现 v0.2+ 功能
- v0.2: NL2SQL + MCP Tool Gateway
- v0.3: 多 Agent 协作 + HITL
- v0.4: 可视化 + 评估体系

## 开发规范

- 改动后运行最小测试：`python -m pytest`
- 保持模块间低耦合，通过接口通信
- 新增模块必须有对应的 `__init__.py`
- Pydantic 模型放在 `app/models/schemas.py`
- Harness 组件放在 `app/harness/` 对应子模块

## 不要做的事

- 不要提前实现 NL2SQL
- 不要提前接入 MCP 远程工具
- 不要提前实现多 Agent 协作
- 不要提前实现 HITL 审批流
- 不要接入真实 LLM API

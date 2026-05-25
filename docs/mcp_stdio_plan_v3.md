# Phase 3 规划：Real MCP Stdio Client（设计文档）

> 范围：仅设计与风险拆解，不改业务代码，不实现真实 MCP stdio。

## 1. 当前 MCP 状态审查

### 1.1 FakeMCPClient 当前如何工作

- 位置：`app/tools/mcp/client.py`
- `FakeMCPClient.list_tools()` 固定返回 3 个工具：
  - `date_lookup`
  - `calculator`
  - `rule_lookup`
- `FakeMCPClient.call_tool(name, arguments)` 为本地内存实现：
  - 正常返回 dict 结果
  - 异常/未知工具返回 `{"error": ...}`
- `MCPToolInfo` 已包含 `input_schema/output_schema/risk_level/permission_scope`，可直接映射到 `ToolSpec`。

### 1.2 StdioMCPClient 当前真实能力边界

- 位置：`app/tools/mcp/stdio_client.py`
- 当前是占位实现：
  - 校验 `MCP_SERVER_COMMAND` 是否配置（`_ensure_configured`）
  - `list_tools()`：未配置 command 时记录 warning 并返回空列表
  - `call_tool()`：未配置 command 返回 error；已配置时也返回“尚未实现真实协议调用”
- **尚未实现**：
  - 子进程启动
  - JSON-RPC 收发
  - initialize handshake
  - tools/list、tools/call
  - timeout/crash/stderr 捕获

### 1.3 ToolGateway 如何 register / discover / call MCP tools

- 位置：`app/harness/gateway/tool_gateway.py`
- `register_mcp_server(server_name, client)`：注册 MCP client
- `discover_mcp_tools(server_name)`：
  - 调用 `client.list_tools()`
  - 把 `MCPToolInfo -> ToolSpec`
  - `source="mcp"`，`is_local=False`，并写入 `_registry`
- `call(tool_name, arguments)`：
  - 根据 `ToolSpec.source` 分流 local/mcp
  - MCP 路径调用 `_call_mcp()`，并把失败统一转 `ToolCallRecord(status=failed, success=False)`
  - 不抛未处理异常到上层 API

### 1.4 MCP_MODE=fake / real 配置链路

- 配置入口：`app/core/config.py`
  - `mcp_mode`（默认 `fake`）
  - `mcp_server_name`
  - `mcp_server_command`
  - `mcp_server_args`
  - `mcp_server_timeout_seconds`
- 运行时接入：`app/main.py::_register_mcp_tools`
  - `mcp_mode=="real"`：构造 `StdioMCPClient` 并 discover
  - discover 为空仅 warning，不中断服务
  - `mcp_mode!=real`：使用 `FakeMCPClient`

### 1.5 当前测试覆盖范围

- `tests/test_mcp_gateway_v03.py`
  - FakeMCPClient 工具发现
  - ToolGateway discover/register/call（MCP + local）
  - `/tools`、`/tools/{name}/call`、`/tasks` 关键链路（在 fake 模式）
- `tests/test_v03_closure_mcp_docker.py`
  - `MCP_MODE=fake` 时 MCP 工具可见
  - `MCP_MODE=real` + 空 command 不崩溃
  - StdioMCPClient 未配置 command 的报错行为
  - Docker 基础文件存在性
- 结论：已覆盖“fake 可用 + real 占位不崩溃”，未覆盖真实 stdio 协议。

---

## 2. Phase 3 目标

目标是在**不改变 ToolGateway API 语义**前提下，实现真实 MCP stdio JSON-RPC client：

1. 支持 `initialize`
2. 支持 `tools/list`
3. 支持 `tools/call`
4. 支持 timeout / process crash / stderr capture
5. 支持失败 fallback（fake 或 local tools）
6. 继续通过 ToolGateway 暴露统一 `ToolSpec`

---

## 3. 协议设计

### 3.1 stdio process 启动方式

- 使用 `subprocess.Popen([...], stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, shell=False)`
- command/args 分离，禁止拼接 shell 字符串
- 启动后进入 handshake 阶段（先 initialize）

### 3.2 JSON-RPC request / response id 管理

- 使用单调递增 `request_id`（int）
- 每个请求维护 `pending[request_id]`（含开始时间、超时、future）
- 响应按 id 路由；未知 id 记录协议错误并忽略

### 3.3 initialize handshake

- 启动后第一步发送 `initialize`（声明 client capabilities）
- 收到成功响应后再允许 `tools/list` / `tools/call`
- initialize 失败：标记 client unavailable，触发 fallback

### 3.4 tools/list schema 映射到 ToolSpec

- MCP `tools/list` -> list[tool]
- 每个 tool 映射：
  - `name -> tool_name`
  - `description`
  - `inputSchema -> input_schema`
  - `output schema`（若无则默认 `{}`）
- 缺省策略：
  - `risk_level`: 默认 `medium`（除非 MCP server 明确声明 read-only）
  - `permission_scope`: 默认 `read`
- 映射失败项跳过并记录 warning

### 3.5 tools/call 参数与返回值映射

- 请求：`name + arguments`
- 响应：
  - 成功：返回 result dict（ToolGateway 判定 success）
  - 失败：返回 `{"error": ...}`（ToolGateway 生成 failed record）

### 3.6 错误码和异常类型设计

建议异常分层：

- `MCPConfigError`：配置错误（command/allowlist）
- `MCPProtocolError`：JSON-RPC 格式错误/未知响应
- `MCPTimeoutError`：请求超时
- `MCPProcessCrashedError`：子进程异常退出
- `MCPToolNotFoundError`：工具不存在

### 3.7 超时与取消策略

- 单请求超时：`MCP_SERVER_TIMEOUT_SECONDS`
- 超时后：
  - 该请求返回 error
  - 不立即 kill 全进程（可配置）
  - 连续超时达到阈值触发重启
- 取消策略：Phase 3 优先“超时即失败”，不强依赖 server-side cancel

---

## 4. 安全设计

1. **command allowlist**
   - 仅允许白名单命令启动 MCP server
2. **args allowlist / validation**
   - 参数格式校验；禁止危险 flag（如可执行任意 shell 的参数）
3. **working directory 限制**
   - 限定在配置目录或仓库允许目录
4. **env whitelist**
   - 仅透传显式允许环境变量
5. **禁止 `shell=True`**
6. **stdout/stderr 最大长度**
   - 防日志爆炸/内存风险
7. **risk_level 默认策略**
   - 未声明风险等级时默认 `medium`，仅在 MCP server 明确声明 read-only 时可降为 `low`
8. **permission_scope 默认策略**
   - 默认 `read`
9. **prompt injection 不应污染 MCP command**
   - command/args 必须来自配置，不来自用户 query/prompt

---

## 5. 生命周期设计

### 5.1 lazy start vs app startup start

- 推荐：**lazy start + 首次 discover 时启动**
- 原因：减少启动时外部依赖失败对主服务可用性的影响

### 5.2 healthcheck

- 提供 client 内部健康状态：
  - process alive
  - initialized
  - recent error

### 5.3 process restart

- crash/连续协议错误/连续超时后自动重启
- 重启后重新 initialize + tools/list

### 5.4 shutdown cleanup

- app 退出时优雅关闭 stdin/stdout/stderr + terminate/kill 兜底

### 5.5 并发调用锁或请求队列

- Phase 3 建议单进程单连接 + 请求队列
- 保证 request_id 和读写线程安全

### 5.6 Windows / Linux 差异

- 路径/命令解析差异
- 换行符与编码差异
- 进程终止行为差异（terminate/kill）

---

## 6. 配置设计

现有：

- `MCP_MODE`
- `MCP_SERVER_NAME`
- `MCP_SERVER_COMMAND`
- `MCP_SERVER_ARGS`
- `MCP_SERVER_TIMEOUT_SECONDS`

建议新增：

- `MCP_SERVER_WORKDIR`
- `MCP_SERVER_ENV_ALLOWLIST`
- `MCP_SERVER_COMMAND_ALLOWLIST`（建议新增）

说明：

- 默认保持 `MCP_MODE=fake`，不破坏现有行为
- 未配置 command 或不在 allowlist 时，real 模式降级不可用并告警

---

## 7. 测试计划

### 7.1 fake stdio MCP server 脚本

- 新增测试辅助脚本（仅测试目录）模拟 JSON-RPC server

### 7.2 协议层测试

1. initialize success
2. tools/list success
3. tools/call success
4. invalid JSON
5. timeout
6. process crash
7. unknown tool
8. command not allowlisted

### 7.3 集成测试

- ToolGateway discover/call integration（real 模式 + fake stdio server）
- `/tools` / `/tools/{name}/call` 在 real 模式可走通

### 7.4 回归保证

- `MCP_MODE=fake` 旧测试不变
- 当前 v2.1.0 全量测试继续通过

---

## 8. 分阶段实现路线

### Phase 3.1 protocol client skeleton + fake stdio server tests

状态：已完成 Phase 3.1（protocol skeleton + initialize tests）。

- 搭建进程管理、JSON-RPC 基础收发、initialize
- 增加 fake stdio server 测试

### Phase 3.2 tools/list -> ToolSpec mapping

状态：已完成 Phase 3.2（tools/list -> MCPToolInfo/ToolSpec mapping）。

- 完成 list 映射和字段缺省策略（`risk_level` 缺省 `medium`）
- 接入 ToolGateway discover（real + fake stdio server）
- `app.main` real-mode 注册链路已将 `workdir/env_allowlist/command_allowlist` 透传到 `StdioMCPClient`
- `tools/call` 仍未实现，保留至 Phase 3.3

### Phase 3.3 tools/call integration

状态：已完成 Phase 3.3（tools/call integration，基于 fake stdio server 协议验收）。

- 完成 `tools/call` 请求映射与错误传递（JSON-RPC error/timeout/crash/protocol error -> `{"error": ...}`）
- 保持 ToolGateway 返回 `ToolCallRecord` 语义不变
- 真实外部 MCP Server 尚未验收，仅完成 fake stdio server 协议链路

### Phase 3.4 lifecycle / timeout / crash recovery

- 加入超时、重启、健康状态、并发队列

### Phase 3.5 security hardening + docs + release cleanup

- command/args/env/workdir 安全收敛
- 文档、验收、release 口径更新

---

## 9. 非目标

1. 不接真实 LLM
2. 不做前端
3. 不实现多 MCP server 管理平台
4. 不改变 graph runtime
5. 不让 MCP tool 绕过 ToolGateway / PolicyEngine / Audit / Metrics

---

## 10. 风险清单（优先级）

- P0：子进程崩溃导致调用阻塞或资源泄漏
- P0：配置注入导致执行不安全 command
- P1：JSON-RPC 响应错配（id 混乱）导致结果污染
- P1：timeout 策略不当导致重复调用/雪崩
- P2：跨平台行为差异导致 CI 与本地不一致

缓解原则：先协议正确性，再生命周期，再安全加固，最后文档与发布。

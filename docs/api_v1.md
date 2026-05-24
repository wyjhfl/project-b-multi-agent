# Project B: Harness-native 运营中台 Agent — API v1.0 文档

> 版本：v1.0  
> 基础路径：`http://<host>:<port>`  
> 所有请求/响应均为 JSON 格式，`Content-Type: application/json`

---

## 目录

1. [Health 健康检查](#1-health-健康检查)
2. [Tasks 任务管理](#2-tasks-任务管理)
3. [NL2SQL 自然语言转 SQL](#3-nl2sql-自然语言转-sql)
4. [Tools 工具调用](#4-tools-工具调用)
5. [Approvals 审批管理](#5-approvals-审批管理)
6. [Audit 审计日志](#6-audit-审计日志)
7. [Metrics 指标统计](#7-metrics-指标统计)
8. [Runtime Snapshot 运行时快照](#8-runtime-snapshot-运行时快照)
9. [Eval 评测](#9-eval-评测)
10. [Memory / Skills / Reflection 记忆/技能/反思](#10-memory--skills--reflection-记忆技能反思)

---

## 1. Health 健康检查

### `GET /health`

服务健康检查，返回当前运行状态。

**请求示例：**

```bash
curl http://localhost:8000/health
```

**响应关键字段：**

| 字段    | 类型   | 说明           |
| ------- | ------ | -------------- |
| status  | string | 服务状态，`"ok"` 表示正常 |

**响应示例：**

```json
{
  "status": "ok"
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

## 2. Tasks 任务管理

### `POST /tasks`

创建并执行一个新任务。支持多种执行模式，包括关键词、NL2SQL、多工具、多 Agent 及自动模式。

**请求体：**

| 字段              | 类型    | 必填 | 说明                                                                 |
| ----------------- | ------- | ---- | -------------------------------------------------------------------- |
| query             | string  | ✅   | 用户查询文本                                                         |
| mode              | string  | ❌   | 执行模式：`keyword` / `nl2sql` / `multitool` / `multi_agent` / `auto`，默认 `auto` |
| generator         | string  | ❌   | SQL 生成器名称                                                       |
| provider          | string  | ❌   | LLM 提供商名称                                                       |
| fallback_to_mock  | boolean | ❌   | LLM 不可用时是否回退到 Mock，默认 `false`                            |
| session_id        | string  | ❌   | 会话 ID，用于关联上下文记忆                                          |

**请求示例：**

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "query": "查询上周各渠道的订单量",
    "mode": "multi_agent",
    "generator": "default",
    "provider": "openai",
    "fallback_to_mock": true,
    "session_id": "sess_abc123"
  }'
```

**响应关键字段：**

| 字段        | 类型   | 说明                          |
| ----------- | ------ | ----------------------------- |
| task_id     | string | 任务唯一标识                  |
| status      | string | 任务状态：`pending` / `running` / `completed` / `failed` |
| result      | object | 任务执行结果（完成时返回）    |
| created_at  | string | 任务创建时间（ISO 8601）      |

**响应示例：**

```json
{
  "task_id": "task_20260524_001",
  "status": "running",
  "result": null,
  "created_at": "2026-05-24T10:30:00+08:00"
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ✅         | ❌         | ✅           |

---

### `GET /tasks`

获取任务列表。

**查询参数：**

| 字段 | 类型 | 必填 | 说明                     |
| ---- | ---- | ---- | ------------------------ |
| limit | int  | ❌   | 返回条数上限，默认 20    |

**请求示例：**

```bash
curl http://localhost:8000/tasks?limit=10
```

**响应关键字段：**

| 字段  | 类型   | 说明         |
| ----- | ------ | ------------ |
| items | array  | 任务摘要列表 |
| total | int    | 任务总数     |

**响应示例：**

```json
{
  "items": [
    {
      "task_id": "task_20260524_001",
      "status": "completed",
      "query": "查询上周各渠道的订单量",
      "created_at": "2026-05-24T10:30:00+08:00"
    }
  ],
  "total": 1
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `GET /tasks/{task_id}`

获取单个任务的详细信息。

**路径参数：**

| 字段     | 类型   | 说明       |
| -------- | ------ | ---------- |
| task_id  | string | 任务唯一标识 |

**请求示例：**

```bash
curl http://localhost:8000/tasks/task_20260524_001
```

**响应关键字段：**

| 字段        | 类型   | 说明                          |
| ----------- | ------ | ----------------------------- |
| task_id     | string | 任务唯一标识                  |
| status      | string | 任务状态                      |
| query       | string | 原始查询文本                  |
| mode        | string | 执行模式                      |
| result      | object | 任务执行结果                  |
| error       | string | 错误信息（失败时返回）        |
| created_at  | string | 创建时间                      |
| updated_at  | string | 最后更新时间                  |

**响应示例：**

```json
{
  "task_id": "task_20260524_001",
  "status": "completed",
  "query": "查询上周各渠道的订单量",
  "mode": "multi_agent",
  "result": {
    "data": [
      { "channel": "线上", "order_count": 1520 },
      { "channel": "线下", "order_count": 830 }
    ]
  },
  "error": null,
  "created_at": "2026-05-24T10:30:00+08:00",
  "updated_at": "2026-05-24T10:30:05+08:00"
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `GET /tasks/{task_id}/trace`

获取指定任务的完整执行链路追踪。

**路径参数：**

| 字段     | 类型   | 说明       |
| -------- | ------ | ---------- |
| task_id  | string | 任务唯一标识 |

**请求示例：**

```bash
curl http://localhost:8000/tasks/task_20260524_001/trace
```

**响应关键字段：**

| 字段         | 类型   | 说明                                  |
| ------------ | ------ | ------------------------------------- |
| task_id      | string | 任务唯一标识                          |
| events       | array  | 按时间排序的 trace 事件列表           |
| events[].step | string | 步骤名称                              |
| events[].timestamp | string | 事件时间戳（ISO 8601）          |
| events[].duration_ms | int | 步骤耗时（毫秒）                  |
| events[].detail | object | 步骤详情                          |

**响应示例：**

```json
{
  "task_id": "task_20260524_001",
  "events": [
    {
      "step": "query_parse",
      "timestamp": "2026-05-24T10:30:00.100+08:00",
      "duration_ms": 120,
      "detail": { "intent": "order_query", "entities": ["上周", "各渠道"] }
    },
    {
      "step": "sql_generate",
      "timestamp": "2026-05-24T10:30:00.250+08:00",
      "duration_ms": 850,
      "detail": { "sql": "SELECT channel, COUNT(*) AS order_count FROM orders WHERE ...", "generator": "default" }
    },
    {
      "step": "sql_execute",
      "timestamp": "2026-05-24T10:30:01.100+08:00",
      "duration_ms": 340,
      "detail": { "rows": 2 }
    }
  ]
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

## 3. NL2SQL 自然语言转 SQL

### `POST /nl2sql/preview`

预览自然语言转 SQL 的结果，仅生成 SQL 不执行。

**请求体：**

| 字段             | 类型    | 必填 | 说明                                      |
| ---------------- | ------- | ---- | ----------------------------------------- |
| query            | string  | ✅   | 自然语言查询文本                          |
| generator        | string  | ❌   | SQL 生成器名称                            |
| provider         | string  | ❌   | LLM 提供商名称                            |
| fallback_to_mock | boolean | ❌   | LLM 不可用时是否回退到 Mock，默认 `false` |

**请求示例：**

```bash
curl -X POST http://localhost:8000/nl2sql/preview \
  -H "Content-Type: application/json" \
  -d '{
    "query": "上个月销售额最高的前5个产品",
    "generator": "default",
    "provider": "openai",
    "fallback_to_mock": true
  }'
```

**响应关键字段：**

| 字段       | 类型    | 说明                          |
| ---------- | ------- | ----------------------------- |
| sql        | string  | 生成的 SQL 语句               |
| generator  | string  | 实际使用的生成器              |
| is_mock    | boolean | 是否使用了 Mock 生成          |
| tables     | array   | 涉及的表名列表                |

**响应示例：**

```json
{
  "sql": "SELECT product_name, SUM(amount) AS total_sales FROM orders WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') GROUP BY product_name ORDER BY total_sales DESC LIMIT 5",
  "generator": "default",
  "is_mock": false,
  "tables": ["orders"]
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ✅         | ❌         | ❌           |

---

### `POST /nl2sql/execute`

将自然语言转为 SQL 并执行，返回查询结果。

**请求体：**

| 字段             | 类型    | 必填 | 说明                                      |
| ---------------- | ------- | ---- | ----------------------------------------- |
| query            | string  | ✅   | 自然语言查询文本                          |
| generator        | string  | ❌   | SQL 生成器名称                            |
| provider         | string  | ❌   | LLM 提供商名称                            |
| fallback_to_mock | boolean | ❌   | LLM 不可用时是否回退到 Mock，默认 `false` |

**请求示例：**

```bash
curl -X POST http://localhost:8000/nl2sql/execute \
  -H "Content-Type: application/json" \
  -d '{
    "query": "上个月销售额最高的前5个产品",
    "generator": "default",
    "provider": "openai",
    "fallback_to_mock": false
  }'
```

**响应关键字段：**

| 字段       | 类型    | 说明                          |
| ---------- | ------- | ----------------------------- |
| sql        | string  | 生成的 SQL 语句               |
| rows       | array   | 查询结果行                    |
| row_count  | int     | 结果行数                      |
| generator  | string  | 实际使用的生成器              |
| is_mock    | boolean | 是否使用了 Mock 生成          |
| execution_ms | int   | SQL 执行耗时（毫秒）          |

**响应示例：**

```json
{
  "sql": "SELECT product_name, SUM(amount) AS total_sales FROM orders WHERE ...",
  "rows": [
    { "product_name": "产品A", "total_sales": 128000 },
    { "product_name": "产品B", "total_sales": 96500 }
  ],
  "row_count": 2,
  "generator": "default",
  "is_mock": false,
  "execution_ms": 210
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ✅         | ❌         | ✅           |

---

### `POST /nl2sql/eval`

对 NL2SQL 生成质量进行评测。

**请求体：**

| 字段        | 类型    | 必填 | 说明                                |
| ----------- | ------- | ---- | ----------------------------------- |
| generator   | string  | ❌   | 待评测的 SQL 生成器名称             |
| provider    | string  | ❌   | LLM 提供商名称                      |
| execute_sql | boolean | ❌   | 是否实际执行生成的 SQL，默认 `false` |

**请求示例：**

```bash
curl -X POST http://localhost:8000/nl2sql/eval \
  -H "Content-Type: application/json" \
  -d '{
    "generator": "default",
    "provider": "openai",
    "execute_sql": true
  }'
```

**响应关键字段：**

| 字段           | 类型   | 说明                              |
| -------------- | ------ | --------------------------------- |
| total          | int    | 评测用例总数                      |
| passed         | int    | 通过数                            |
| failed         | int    | 失败数                            |
| accuracy       | float  | 准确率（0.0 ~ 1.0）               |
| details        | array  | 各用例评测详情                    |
| details[].query | string | 原始查询                          |
| details[].expected_sql | string | 期望 SQL                  |
| details[].actual_sql   | string | 实际生成 SQL              |
| details[].match | bool  | 是否匹配                          |

**响应示例：**

```json
{
  "total": 20,
  "passed": 17,
  "failed": 3,
  "accuracy": 0.85,
  "details": [
    {
      "query": "查询所有订单",
      "expected_sql": "SELECT * FROM orders",
      "actual_sql": "SELECT * FROM orders",
      "match": true
    }
  ]
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ✅         | ❌         | ❌           |

---

## 4. Tools 工具调用

### `GET /tools`

列出所有可用工具，包括本地注册工具和 MCP（Model Context Protocol）远程工具。

**请求示例：**

```bash
curl http://localhost:8000/tools
```

**响应关键字段：**

| 字段              | 类型   | 说明                   |
| ----------------- | ------ | ---------------------- |
| local_tools       | array  | 本地工具列表           |
| mcp_tools         | array  | MCP 远程工具列表       |
| local_tools[].name | string | 工具名称              |
| local_tools[].description | string | 工具描述      |
| local_tools[].parameters | object | 工具参数 Schema |
| mcp_tools[].name  | string | MCP 工具名称           |
| mcp_tools[].server | string | MCP 服务器标识        |

**响应示例：**

```json
{
  "local_tools": [
    {
      "name": "sql_query",
      "description": "执行 SQL 查询并返回结果",
      "parameters": {
        "type": "object",
        "properties": {
          "sql": { "type": "string", "description": "SQL 语句" }
        },
        "required": ["sql"]
      }
    }
  ],
  "mcp_tools": [
    {
      "name": "web_search",
      "description": "搜索互联网信息",
      "server": "mcp-search-server",
      "parameters": {
        "type": "object",
        "properties": {
          "keywords": { "type": "string" }
        }
      }
    }
  ]
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `POST /tools/{tool_name}/call`

调用指定工具并返回执行结果。

**路径参数：**

| 字段      | 类型   | 说明   |
| --------- | ------ | ------ |
| tool_name | string | 工具名称 |

**请求体：**

| 字段      | 类型   | 必填 | 说明         |
| --------- | ------ | ---- | ------------ |
| arguments | object | ✅   | 工具调用参数 |

**请求示例：**

```bash
curl -X POST http://localhost:8000/tools/sql_query/call \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "sql": "SELECT COUNT(*) AS total FROM orders WHERE status = '\''completed'\''"
    }
  }'
```

**响应关键字段：**

| 字段     | 类型    | 说明                     |
| -------- | ------- | ------------------------ |
| tool     | string  | 工具名称                 |
| result   | object  | 工具执行结果             |
| success  | boolean | 是否执行成功             |
| error    | string  | 错误信息（失败时返回）   |
| duration_ms | int  | 执行耗时（毫秒）         |

**响应示例：**

```json
{
  "tool": "sql_query",
  "result": {
    "rows": [
      { "total": 45230 }
    ]
  },
  "success": true,
  "error": null,
  "duration_ms": 85
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ✅         | ❌         | ✅           |

---

## 5. Approvals 审批管理

### `GET /approvals`

获取审批单列表。

**查询参数：**

| 字段   | 类型   | 必填 | 说明                                      |
| ------ | ------ | ---- | ----------------------------------------- |
| status | string | ❌   | 筛选状态：`pending` / `approved` / `rejected` |
| limit  | int    | ❌   | 返回条数上限，默认 20                     |

**请求示例：**

```bash
curl http://localhost:8000/approvals?status=pending&limit=10
```

**响应关键字段：**

| 字段           | 类型   | 说明                          |
| -------------- | ------ | ----------------------------- |
| items          | array  | 审批单列表                    |
| items[].id     | string | 审批单 ID                     |
| items[].status | string | 审批状态                      |
| items[].task_id | string | 关联的任务 ID                |
| items[].created_at | string | 创建时间                 |
| total          | int    | 符合条件的审批单总数          |

**响应示例：**

```json
{
  "items": [
    {
      "id": "apr_20260524_001",
      "status": "pending",
      "task_id": "task_20260524_001",
      "created_at": "2026-05-24T10:30:02+08:00"
    }
  ],
  "total": 1
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `GET /approvals/summary`

获取审批单统计摘要。

**请求示例：**

```bash
curl http://localhost:8000/approvals/summary
```

**响应关键字段：**

| 字段     | 类型 | 说明         |
| -------- | ---- | ------------ |
| pending  | int  | 待审批数     |
| approved | int  | 已批准数     |
| rejected | int  | 已拒绝数     |
| total    | int  | 审批单总数   |

**响应示例：**

```json
{
  "pending": 3,
  "approved": 45,
  "rejected": 7,
  "total": 55
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `GET /approvals/{id}`

获取单个审批单详情。

**路径参数：**

| 字段 | 类型   | 说明       |
| ---- | ------ | ---------- |
| id   | string | 审批单 ID  |

**请求示例：**

```bash
curl http://localhost:8000/approvals/apr_20260524_001
```

**响应关键字段：**

| 字段            | 类型   | 说明                          |
| --------------- | ------ | ----------------------------- |
| id              | string | 审批单 ID                     |
| status          | string | 审批状态                      |
| task_id         | string | 关联的任务 ID                 |
| request_type    | string | 审批请求类型（如 `sql_execute`） |
| request_detail  | object | 审批请求详情                  |
| decided_by      | string | 审批人（已审批时返回）        |
| reason          | string | 审批理由（已审批时返回）      |
| created_at      | string | 创建时间                      |
| decided_at      | string | 审批时间（已审批时返回）      |

**响应示例：**

```json
{
  "id": "apr_20260524_001",
  "status": "pending",
  "task_id": "task_20260524_001",
  "request_type": "sql_execute",
  "request_detail": {
    "sql": "DELETE FROM temp_logs WHERE created_at < '2026-04-01'"
  },
  "decided_by": null,
  "reason": null,
  "created_at": "2026-05-24T10:30:02+08:00",
  "decided_at": null
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `GET /approvals/{id}/context`

获取审批单的上下文信息，用于辅助审批决策。

**路径参数：**

| 字段 | 类型   | 说明       |
| ---- | ------ | ---------- |
| id   | string | 审批单 ID  |

**请求示例：**

```bash
curl http://localhost:8000/approvals/apr_20260524_001/context
```

**响应关键字段：**

| 字段            | 类型   | 说明                              |
| --------------- | ------ | --------------------------------- |
| approval_id     | string | 审批单 ID                         |
| task_context    | object | 关联任务的上下文信息              |
| trace_summary   | object | 执行链路摘要                      |
| risk_assessment | object | 风险评估结果                      |
| similar_history | array  | 历史相似审批记录                  |

**响应示例：**

```json
{
  "approval_id": "apr_20260524_001",
  "task_context": {
    "query": "清理过期的临时日志",
    "mode": "multi_agent"
  },
  "trace_summary": {
    "steps": 4,
    "total_duration_ms": 2100
  },
  "risk_assessment": {
    "level": "medium",
    "reason": "涉及 DELETE 操作，影响行数未知"
  },
  "similar_history": [
    {
      "approval_id": "apr_20260520_003",
      "outcome": "approved",
      "reason": "影响行数已确认，属于常规清理"
    }
  ]
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `POST /approvals/{id}/approve`

批准审批单。

**路径参数：**

| 字段 | 类型   | 说明       |
| ---- | ------ | ---------- |
| id   | string | 审批单 ID  |

**请求体：**

| 字段         | 类型    | 必填 | 说明                                      |
| ------------ | ------- | ---- | ----------------------------------------- |
| decided_by   | string  | ✅   | 审批人标识                                |
| reason       | string  | ❌   | 批准理由                                  |
| auto_resume  | boolean | ❌   | 批准后是否自动恢复任务执行，默认 `false`  |

**请求示例：**

```bash
curl -X POST http://localhost:8000/approvals/apr_20260524_001/approve \
  -H "Content-Type: application/json" \
  -d '{
    "decided_by": "admin_zhangsan",
    "reason": "影响行数已确认，属于常规清理操作",
    "auto_resume": true
  }'
```

**响应关键字段：**

| 字段        | 类型    | 说明                          |
| ----------- | ------- | ----------------------------- |
| id          | string  | 审批单 ID                     |
| status      | string  | 更新后的状态（`approved`）    |
| decided_by  | string  | 审批人                        |
| decided_at  | string  | 审批时间                      |
| task_resumed | boolean | 任务是否已自动恢复            |

**响应示例：**

```json
{
  "id": "apr_20260524_001",
  "status": "approved",
  "decided_by": "admin_zhangsan",
  "decided_at": "2026-05-24T10:35:00+08:00",
  "task_resumed": true
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ✅         | ✅         | ❌           |

---

### `POST /approvals/{id}/reject`

拒绝审批单。

**路径参数：**

| 字段 | 类型   | 说明       |
| ---- | ------ | ---------- |
| id   | string | 审批单 ID  |

**请求体：**

| 字段       | 类型   | 必填 | 说明       |
| ---------- | ------ | ---- | ---------- |
| decided_by | string | ✅   | 审批人标识 |
| reason     | string | ❌   | 拒绝理由   |

**请求示例：**

```bash
curl -X POST http://localhost:8000/approvals/apr_20260524_001/reject \
  -H "Content-Type: application/json" \
  -d '{
    "decided_by": "admin_zhangsan",
    "reason": "DELETE 操作风险过高，需进一步评估影响范围"
  }'
```

**响应关键字段：**

| 字段       | 类型   | 说明                          |
| ---------- | ------ | ----------------------------- |
| id         | string | 审批单 ID                     |
| status     | string | 更新后的状态（`rejected`）    |
| decided_by | string | 审批人                        |
| decided_at | string | 审批时间                      |

**响应示例：**

```json
{
  "id": "apr_20260524_001",
  "status": "rejected",
  "decided_by": "admin_zhangsan",
  "decided_at": "2026-05-24T10:35:00+08:00"
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ✅         | ✅         | ❌           |

---

### `POST /approvals/{id}/resume`

手动恢复因审批暂停的任务执行。

**路径参数：**

| 字段 | 类型   | 说明       |
| ---- | ------ | ---------- |
| id   | string | 审批单 ID  |

**请求示例：**

```bash
curl -X POST http://localhost:8000/approvals/apr_20260524_001/resume \
  -H "Content-Type: application/json"
```

**响应关键字段：**

| 字段         | 类型    | 说明                          |
| ------------ | ------- | ----------------------------- |
| id           | string  | 审批单 ID                     |
| task_id      | string  | 关联的任务 ID                 |
| task_status  | string  | 任务恢复后的状态              |
| resumed      | boolean | 是否成功恢复                  |

**响应示例：**

```json
{
  "id": "apr_20260524_001",
  "task_id": "task_20260524_001",
  "task_status": "running",
  "resumed": true
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ✅         | ✅         | ❌           |

---

## 6. Audit 审计日志

### `GET /audit/events`

查询审计事件列表，支持多维度筛选。

**查询参数：**

| 字段       | 类型   | 必填 | 说明                                              |
| ---------- | ------ | ---- | ------------------------------------------------- |
| event_type | string | ❌   | 事件类型（如 `approval` / `tool_call` / `task`）  |
| actor      | string | ❌   | 操作人标识                                        |
| task_id    | string | ❌   | 关联的任务 ID                                     |
| outcome    | string | ❌   | 事件结果（`success` / `failure`）                 |
| severity   | string | ❌   | 严重级别（`info` / `warn` / `error` / `critical`） |
| start_time | string | ❌   | 起始时间（ISO 8601）                              |
| end_time   | string | ❌   | 结束时间（ISO 8601）                              |
| limit      | int    | ❌   | 返回条数上限，默认 50                             |

**请求示例：**

```bash
curl "http://localhost:8000/audit/events?event_type=approval&severity=warn&limit=20"
```

**响应关键字段：**

| 字段             | 类型   | 说明                          |
| ---------------- | ------ | ----------------------------- |
| items            | array  | 审计事件列表                  |
| items[].event_id | string | 事件唯一标识                  |
| items[].event_type | string | 事件类型                    |
| items[].actor    | string | 操作人                        |
| items[].outcome  | string | 事件结果                      |
| items[].severity | string | 严重级别                      |
| items[].timestamp | string | 事件时间戳                    |
| items[].detail   | object | 事件详情                      |
| total            | int    | 符合条件的事件总数            |

**响应示例：**

```json
{
  "items": [
    {
      "event_id": "evt_20260524_001",
      "event_type": "approval",
      "actor": "admin_zhangsan",
      "outcome": "success",
      "severity": "info",
      "timestamp": "2026-05-24T10:35:00+08:00",
      "detail": {
        "action": "approve",
        "approval_id": "apr_20260524_001",
        "reason": "影响行数已确认，属于常规清理操作"
      }
    }
  ],
  "total": 1
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `GET /audit/events/{event_id}`

获取单个审计事件的详细信息。

**路径参数：**

| 字段     | 类型   | 说明       |
| -------- | ------ | ---------- |
| event_id | string | 事件唯一标识 |

**请求示例：**

```bash
curl http://localhost:8000/audit/events/evt_20260524_001
```

**响应关键字段：**

| 字段        | 类型   | 说明                          |
| ----------- | ------ | ----------------------------- |
| event_id    | string | 事件唯一标识                  |
| event_type  | string | 事件类型                      |
| actor       | string | 操作人                        |
| task_id     | string | 关联的任务 ID                 |
| outcome     | string | 事件结果                      |
| severity    | string | 严重级别                      |
| timestamp   | string | 事件时间戳                    |
| detail      | object | 事件完整详情                  |
| context     | object | 事件上下文（关联 trace 等）   |

**响应示例：**

```json
{
  "event_id": "evt_20260524_001",
  "event_type": "approval",
  "actor": "admin_zhangsan",
  "task_id": "task_20260524_001",
  "outcome": "success",
  "severity": "info",
  "timestamp": "2026-05-24T10:35:00+08:00",
  "detail": {
    "action": "approve",
    "approval_id": "apr_20260524_001",
    "reason": "影响行数已确认，属于常规清理操作",
    "auto_resume": true
  },
  "context": {
    "trace_id": "trace_20260524_001",
    "session_id": "sess_abc123"
  }
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

## 7. Metrics 指标统计

### `GET /metrics/runtime`

获取内存中的运行时指标摘要。

**请求示例：**

```bash
curl http://localhost:8000/metrics/runtime
```

**响应关键字段：**

| 字段                  | 类型   | 说明                          |
| --------------------- | ------ | ----------------------------- |
| uptime_seconds        | int    | 服务运行时长（秒）            |
| tasks_total           | int    | 任务总数                      |
| tasks_completed       | int    | 已完成任务数                  |
| tasks_failed          | int    | 失败任务数                    |
| tool_calls_total      | int    | 工具调用总次数                |
| approvals_pending     | int    | 当前待审批数                  |
| llm_calls_total       | int    | LLM 调用总次数                |
| llm_tokens_total      | int    | LLM Token 消耗总量            |
| active_sessions       | int    | 活跃会话数                    |

**响应示例：**

```json
{
  "uptime_seconds": 86400,
  "tasks_total": 1520,
  "tasks_completed": 1403,
  "tasks_failed": 117,
  "tool_calls_total": 4830,
  "approvals_pending": 3,
  "llm_calls_total": 3200,
  "llm_tokens_total": 12500000,
  "active_sessions": 12
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `GET /metrics/cost/summary`

获取成本统计摘要（数据来源：SQLite）。

**查询参数：**

| 字段       | 类型   | 必填 | 说明                     |
| ---------- | ------ | ---- | ------------------------ |
| start_time | string | ❌   | 起始时间（ISO 8601）     |
| end_time   | string | ❌   | 结束时间（ISO 8601）     |
| limit      | int    | ❌   | 返回条数上限，默认 50    |

**请求示例：**

```bash
curl "http://localhost:8000/metrics/cost/summary?start_time=2026-05-01T00:00:00%2B08:00&end_time=2026-05-24T23:59:59%2B08:00&limit=30"
```

**响应关键字段：**

| 字段              | 类型   | 说明                          |
| ----------------- | ------ | ----------------------------- |
| total_cost_usd    | float  | 总成本（美元）                |
| total_tokens      | int    | 总 Token 消耗                 |
| by_provider       | array  | 按提供商汇总                  |
| by_provider[].provider | string | 提供商名称              |
| by_provider[].cost_usd  | float  | 该提供商成本             |
| by_provider[].tokens    | int    | 该提供商 Token 消耗      |
| by_day            | array  | 按日汇总                      |
| by_day[].date     | string | 日期                          |
| by_day[].cost_usd | float  | 当日成本                      |

**响应示例：**

```json
{
  "total_cost_usd": 125.60,
  "total_tokens": 12500000,
  "by_provider": [
    {
      "provider": "openai",
      "cost_usd": 98.40,
      "tokens": 9800000
    },
    {
      "provider": "anthropic",
      "cost_usd": 27.20,
      "tokens": 2700000
    }
  ],
  "by_day": [
    {
      "date": "2026-05-24",
      "cost_usd": 8.50
    }
  ]
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `GET /metrics/tools/summary`

获取工具调用统计摘要（数据来源：SQLite）。

**查询参数：**

| 字段       | 类型   | 必填 | 说明                     |
| ---------- | ------ | ---- | ------------------------ |
| start_time | string | ❌   | 起始时间（ISO 8601）     |
| end_time   | string | ❌   | 结束时间（ISO 8601）     |
| limit      | int    | ❌   | 返回条数上限，默认 50    |

**请求示例：**

```bash
curl "http://localhost:8000/metrics/tools/summary?start_time=2026-05-20T00:00:00%2B08:00&limit=20"
```

**响应关键字段：**

| 字段                    | 类型   | 说明                          |
| ----------------------- | ------ | ----------------------------- |
| total_calls             | int    | 工具调用总次数                |
| total_success           | int    | 成功次数                      |
| total_failure           | int    | 失败次数                      |
| by_tool                 | array  | 按工具汇总                    |
| by_tool[].tool_name     | string | 工具名称                      |
| by_tool[].call_count    | int    | 调用次数                      |
| by_tool[].success_count | int    | 成功次数                      |
| by_tool[].avg_duration_ms | float | 平均耗时（毫秒）            |
| by_tool[].failure_count | int    | 失败次数                      |

**响应示例：**

```json
{
  "total_calls": 4830,
  "total_success": 4650,
  "total_failure": 180,
  "by_tool": [
    {
      "tool_name": "sql_query",
      "call_count": 2100,
      "success_count": 2050,
      "avg_duration_ms": 120.5,
      "failure_count": 50
    },
    {
      "tool_name": "web_search",
      "call_count": 850,
      "success_count": 830,
      "avg_duration_ms": 2300.0,
      "failure_count": 20
    }
  ]
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `GET /metrics/tasks/summary`

获取任务统计摘要（数据来源：SQLite）。

**查询参数：**

| 字段       | 类型   | 必填 | 说明                     |
| ---------- | ------ | ---- | ------------------------ |
| start_time | string | ❌   | 起始时间（ISO 8601）     |
| end_time   | string | ❌   | 结束时间（ISO 8601）     |
| limit      | int    | ❌   | 返回条数上限，默认 50    |

**请求示例：**

```bash
curl "http://localhost:8000/metrics/tasks/summary?start_time=2026-05-01T00:00:00%2B08:00&end_time=2026-05-24T23:59:59%2B08:00"
```

**响应关键字段：**

| 字段                    | 类型   | 说明                          |
| ----------------------- | ------ | ----------------------------- |
| total_tasks             | int    | 任务总数                      |
| total_completed         | int    | 已完成数                      |
| total_failed            | int    | 失败数                        |
| avg_duration_ms         | float  | 平均任务耗时（毫秒）          |
| by_mode                 | array  | 按执行模式汇总                |
| by_mode[].mode          | string | 执行模式                      |
| by_mode[].count         | int    | 该模式任务数                  |
| by_mode[].success_rate  | float  | 成功率（0.0 ~ 1.0）           |
| by_mode[].avg_duration_ms | float | 该模式平均耗时（毫秒）      |

**响应示例：**

```json
{
  "total_tasks": 1520,
  "total_completed": 1403,
  "total_failed": 117,
  "avg_duration_ms": 3200.0,
  "by_mode": [
    {
      "mode": "multi_agent",
      "count": 680,
      "success_rate": 0.95,
      "avg_duration_ms": 4500.0
    },
    {
      "mode": "nl2sql",
      "count": 520,
      "success_rate": 0.88,
      "avg_duration_ms": 1800.0
    },
    {
      "mode": "keyword",
      "count": 320,
      "success_rate": 0.97,
      "avg_duration_ms": 200.0
    }
  ]
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

## 8. Runtime Snapshot 运行时快照

### `GET /runtime/snapshot`

获取运行时全量快照，聚合应用版本、指标、成本、任务、工具、审计、内存和技能等摘要信息。

**请求示例：**

```bash
curl http://localhost:8000/runtime/snapshot
```

**响应关键字段：**

| 字段                     | 类型   | 说明                          |
| ------------------------ | ------ | ----------------------------- |
| app_version              | string | 应用版本号                    |
| snapshot_time            | string | 快照生成时间（ISO 8601）      |
| metrics                  | object | 运行时指标摘要                |
| cost                     | object | 成本摘要                      |
| task                     | object | 任务摘要                      |
| tool                     | object | 工具摘要                      |
| audit                    | object | 审计摘要                      |
| memory                   | object | 内存/会话摘要                 |
| skills                   | object | 技能摘要                      |

**响应示例：**

```json
{
  "app_version": "1.0.0",
  "snapshot_time": "2026-05-24T10:40:00+08:00",
  "metrics": {
    "uptime_seconds": 86400,
    "tasks_total": 1520,
    "tasks_completed": 1403,
    "tasks_failed": 117,
    "tool_calls_total": 4830,
    "llm_calls_total": 3200,
    "llm_tokens_total": 12500000,
    "active_sessions": 12
  },
  "cost": {
    "total_cost_usd": 125.60,
    "total_tokens": 12500000
  },
  "task": {
    "total_tasks": 1520,
    "total_completed": 1403,
    "total_failed": 117,
    "avg_duration_ms": 3200.0
  },
  "tool": {
    "total_calls": 4830,
    "total_success": 4650,
    "total_failure": 180
  },
  "audit": {
    "total_events": 9800,
    "by_severity": {
      "info": 8500,
      "warn": 1100,
      "error": 180,
      "critical": 20
    }
  },
  "memory": {
    "active_sessions": 12,
    "total_messages": 5600
  },
  "skills": {
    "total_skills": 8,
    "total_matches": 3200
  }
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

## 9. Eval 评测

### `GET /eval/summary`

获取评测结果摘要。

**请求示例：**

```bash
curl http://localhost:8000/eval/summary
```

**响应关键字段：**

| 字段              | 类型   | 说明                          |
| ----------------- | ------ | ----------------------------- |
| nl2sql_accuracy   | float  | NL2SQL 准确率                 |
| multitool_success_rate | float | 多工具成功率              |
| multi_agent_success_rate | float | 多 Agent 成功率          |
| total_eval_runs   | int    | 评测总运行次数                |
| last_run_time     | string | 最近一次评测时间              |

**响应示例：**

```json
{
  "nl2sql_accuracy": 0.85,
  "multitool_success_rate": 0.91,
  "multi_agent_success_rate": 0.88,
  "total_eval_runs": 45,
  "last_run_time": "2026-05-24T09:00:00+08:00"
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `POST /eval/run-all`

运行全部评测套件。

**请求示例：**

```bash
curl -X POST http://localhost:8000/eval/run-all \
  -H "Content-Type: application/json"
```

**响应关键字段：**

| 字段            | 类型   | 说明                          |
| --------------- | ------ | ----------------------------- |
| run_id          | string | 评测运行 ID                   |
| status          | string | 运行状态                      |
| suites          | array  | 各套件运行结果                |
| suites[].name   | string | 套件名称                      |
| suites[].total  | int    | 用例总数                      |
| suites[].passed | int    | 通过数                        |
| suites[].failed | int    | 失败数                        |
| suites[].accuracy | float | 准确率                      |
| started_at      | string | 开始时间                      |
| completed_at    | string | 完成时间                      |

**响应示例：**

```json
{
  "run_id": "eval_20260524_001",
  "status": "completed",
  "suites": [
    {
      "name": "nl2sql",
      "total": 20,
      "passed": 17,
      "failed": 3,
      "accuracy": 0.85
    },
    {
      "name": "multitool",
      "total": 15,
      "passed": 14,
      "failed": 1,
      "accuracy": 0.93
    },
    {
      "name": "multi_agent",
      "total": 10,
      "passed": 9,
      "failed": 1,
      "accuracy": 0.90
    }
  ],
  "started_at": "2026-05-24T10:00:00+08:00",
  "completed_at": "2026-05-24T10:05:30+08:00"
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `POST /eval/bad-cases/run`

运行 Bad Case 分析，识别并记录失败用例。

**请求体：**

| 字段      | 类型    | 必填 | 说明                                      |
| --------- | ------- | ---- | ----------------------------------------- |
| use_judge | boolean | ❌   | 是否使用 LLM Judge 评判，默认 `false`     |
| limit     | int     | ❌   | 分析用例上限，默认 50                     |
| suite     | string  | ❌   | 指定评测套件名称                          |

**请求示例：**

```bash
curl -X POST http://localhost:8000/eval/bad-cases/run \
  -H "Content-Type: application/json" \
  -d '{
    "use_judge": true,
    "limit": 20,
    "suite": "nl2sql"
  }'
```

**响应关键字段：**

| 字段                  | 类型   | 说明                          |
| --------------------- | ------ | ----------------------------- |
| run_id                | string | Bad Case 运行 ID              |
| total_analyzed        | int    | 分析用例总数                  |
| bad_cases_found       | int    | 发现的 Bad Case 数量          |
| bad_cases             | array  | Bad Case 详情列表             |
| bad_cases[].query     | string | 原始查询                      |
| bad_cases[].expected  | string | 期望结果                      |
| bad_cases[].actual    | string | 实际结果                      |
| bad_cases[].reason    | string | 失败原因                      |
| bad_cases[].severity  | string | 严重级别                      |

**响应示例：**

```json
{
  "run_id": "badcase_20260524_001",
  "total_analyzed": 20,
  "bad_cases_found": 3,
  "bad_cases": [
    {
      "query": "查询上季度退货率最高的商品",
      "expected": "SELECT product_name, ...",
      "actual": "SELECT name, ...",
      "reason": "表名映射错误：使用了错误的列名",
      "severity": "high"
    }
  ]
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ✅         | ❌         | ❌           |

---

### `GET /eval/bad-cases`

查询已记录的 Bad Case 列表。

**查询参数：**

| 字段  | 类型   | 必填 | 说明               |
| ----- | ------ | ---- | ------------------ |
| suite | string | ❌   | 按评测套件筛选     |
| tag   | string | ❌   | 按标签筛选         |

**请求示例：**

```bash
curl "http://localhost:8000/eval/bad-cases?suite=nl2sql&tag=table_mapping"
```

**响应关键字段：**

| 字段                  | 类型   | 说明                          |
| --------------------- | ------ | ----------------------------- |
| items                 | array  | Bad Case 列表                 |
| items[].id            | string | Bad Case ID                   |
| items[].suite         | string | 所属套件                      |
| items[].query         | string | 原始查询                      |
| items[].expected      | string | 期望结果                      |
| items[].actual        | string | 实际结果                      |
| items[].reason        | string | 失败原因                      |
| items[].tags          | array  | 标签列表                      |
| items[].created_at    | string | 记录时间                      |
| total                 | int    | Bad Case 总数                 |

**响应示例：**

```json
{
  "items": [
    {
      "id": "bc_001",
      "suite": "nl2sql",
      "query": "查询上季度退货率最高的商品",
      "expected": "SELECT product_name, ...",
      "actual": "SELECT name, ...",
      "reason": "表名映射错误：使用了错误的列名",
      "tags": ["table_mapping", "column_error"],
      "created_at": "2026-05-24T10:05:00+08:00"
    }
  ],
  "total": 1
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `POST /tasks/eval/multi-agent`

运行多 Agent 模式的专项评测。

**请求示例：**

```bash
curl -X POST http://localhost:8000/tasks/eval/multi-agent \
  -H "Content-Type: application/json"
```

**响应关键字段：**

| 字段                    | 类型   | 说明                          |
| ----------------------- | ------ | ----------------------------- |
| run_id                  | string | 评测运行 ID                   |
| total_scenarios         | int    | 评测场景总数                  |
| passed                  | int    | 通过数                        |
| failed                  | int    | 失败数                        |
| success_rate            | float  | 成功率（0.0 ~ 1.0）           |
| scenarios               | array  | 各场景评测结果                |
| scenarios[].name        | string | 场景名称                      |
| scenarios[].passed      | bool   | 是否通过                      |
| scenarios[].duration_ms | int    | 场景耗时（毫秒）              |
| scenarios[].detail      | object | 场景详情                      |

**响应示例：**

```json
{
  "run_id": "ma_eval_20260524_001",
  "total_scenarios": 10,
  "passed": 9,
  "failed": 1,
  "success_rate": 0.90,
  "scenarios": [
    {
      "name": "跨表联合查询",
      "passed": true,
      "duration_ms": 5200,
      "detail": { "agents_involved": 3, "tools_used": ["sql_query", "schema_lookup"] }
    },
    {
      "name": "需审批的删除操作",
      "passed": true,
      "duration_ms": 8300,
      "detail": { "agents_involved": 2, "approval_required": true }
    }
  ]
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

## 10. Memory / Skills / Reflection 记忆/技能/反思

### `GET /memory/{session_id}`

获取指定会话的记忆上下文。

**路径参数：**

| 字段       | 类型   | 说明    |
| ---------- | ------ | ------- |
| session_id | string | 会话 ID |

**请求示例：**

```bash
curl http://localhost:8000/memory/sess_abc123
```

**响应关键字段：**

| 字段              | 类型   | 说明                          |
| ----------------- | ------ | ----------------------------- |
| session_id        | string | 会话 ID                       |
| messages          | array  | 会话消息列表                  |
| messages[].role   | string | 角色（`user` / `assistant` / `system`） |
| messages[].content | string | 消息内容                     |
| messages[].timestamp | string | 消息时间戳                |
| summary           | string | 会话摘要（如有）              |
| created_at        | string | 会话创建时间                  |

**响应示例：**

```json
{
  "session_id": "sess_abc123",
  "messages": [
    {
      "role": "user",
      "content": "查询上周各渠道的订单量",
      "timestamp": "2026-05-24T10:30:00+08:00"
    },
    {
      "role": "assistant",
      "content": "上周各渠道订单量如下：线上 1520 单，线下 830 单。",
      "timestamp": "2026-05-24T10:30:05+08:00"
    }
  ],
  "summary": "用户查询了上周各渠道的订单量数据",
  "created_at": "2026-05-24T10:30:00+08:00"
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `DELETE /memory/{session_id}`

删除指定会话的记忆上下文。

**路径参数：**

| 字段       | 类型   | 说明    |
| ---------- | ------ | ------- |
| session_id | string | 会话 ID |

**请求示例：**

```bash
curl -X DELETE http://localhost:8000/memory/sess_abc123
```

**响应关键字段：**

| 字段       | 类型    | 说明                          |
| ---------- | ------- | ----------------------------- |
| session_id | string  | 会话 ID                       |
| deleted    | boolean | 是否删除成功                  |

**响应示例：**

```json
{
  "session_id": "sess_abc123",
  "deleted": true
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `GET /skills`

获取所有已注册技能列表。

**请求示例：**

```bash
curl http://localhost:8000/skills
```

**响应关键字段：**

| 字段               | 类型   | 说明                          |
| ------------------ | ------ | ----------------------------- |
| skills             | array  | 技能列表                      |
| skills[].name      | string | 技能名称                      |
| skills[].description | string | 技能描述                    |
| skills[].keywords  | array  | 触发关键词                    |
| skills[].tools     | array  | 关联的工具列表                |
| total              | int    | 技能总数                      |

**响应示例：**

```json
{
  "skills": [
    {
      "name": "order_analysis",
      "description": "订单数据分析与查询",
      "keywords": ["订单", "销量", "销售额", "退货"],
      "tools": ["sql_query", "chart_generator"]
    },
    {
      "name": "data_cleanup",
      "description": "数据清理与维护操作",
      "keywords": ["清理", "删除", "归档", "过期数据"],
      "tools": ["sql_query"]
    }
  ],
  "total": 2
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `POST /skills/match`

根据查询文本匹配最相关的技能。

**请求体：**

| 字段  | 类型   | 必填 | 说明         |
| ----- | ------ | ---- | ------------ |
| query | string | ✅   | 查询文本     |

**请求示例：**

```bash
curl -X POST http://localhost:8000/skills/match \
  -H "Content-Type: application/json" \
  -d '{
    "query": "帮我分析一下最近的订单趋势"
  }'
```

**响应关键字段：**

| 字段               | 类型   | 说明                          |
| ------------------ | ------ | ----------------------------- |
| matches            | array  | 匹配的技能列表（按相关度排序） |
| matches[].name     | string | 技能名称                      |
| matches[].score    | float  | 匹配得分（0.0 ~ 1.0）         |
| matches[].reason   | string | 匹配原因                      |
| query              | string | 原始查询文本                  |

**响应示例：**

```json
{
  "matches": [
    {
      "name": "order_analysis",
      "score": 0.95,
      "reason": "查询涉及订单分析，匹配关键词：订单"
    },
    {
      "name": "data_cleanup",
      "score": 0.12,
      "reason": "与数据清理关联度较低"
    }
  ],
  "query": "帮我分析一下最近的订单趋势"
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

### `POST /reflection/check`

对任务结果进行反思检查，评估执行质量并生成改进建议。

**请求体：**

| 字段          | 类型   | 必填 | 说明                          |
| ------------- | ------ | ---- | ----------------------------- |
| task_result   | object | ✅   | 任务执行结果                  |
| trace_events  | array  | ❌   | 关联的 trace 事件列表         |
| audit_events  | array  | ❌   | 关联的 audit 事件列表         |

**请求示例：**

```bash
curl -X POST http://localhost:8000/reflection/check \
  -H "Content-Type: application/json" \
  -d '{
    "task_result": {
      "task_id": "task_20260524_001",
      "status": "completed",
      "data": { "rows": 2 }
    },
    "trace_events": [
      { "step": "sql_generate", "duration_ms": 850 },
      { "step": "sql_execute", "duration_ms": 340 }
    ],
    "audit_events": [
      { "event_type": "approval", "outcome": "success" }
    ]
  }'
```

**响应关键字段：**

| 字段                     | 类型   | 说明                          |
| ------------------------ | ------ | ----------------------------- |
| quality_score            | float  | 执行质量评分（0.0 ~ 1.0）     |
| issues                   | array  | 发现的问题列表                |
| issues[].severity        | string | 问题严重级别                  |
| issues[].description     | string | 问题描述                      |
| issues[].suggestion      | string | 改进建议                      |
| improvements             | array  | 改进建议列表                  |
| improvements[].area      | string | 改进领域                      |
| improvements[].action    | string | 建议行动                      |
| improvements[].priority  | string | 优先级（`high` / `medium` / `low`） |

**响应示例：**

```json
{
  "quality_score": 0.82,
  "issues": [
    {
      "severity": "warn",
      "description": "SQL 生成耗时偏高（850ms），可能存在 Prompt 优化空间",
      "suggestion": "精简 Schema 描述，减少无关表信息传入"
    }
  ],
  "improvements": [
    {
      "area": "sql_generation",
      "action": "缓存常用查询的 Schema 片段，减少 Prompt 长度",
      "priority": "medium"
    },
    {
      "area": "approval_flow",
      "action": "对低风险 DELETE 操作设置自动审批规则",
      "priority": "low"
    }
  ]
}
```

| 写入 trace | 写入 audit | 写入 metrics |
| ---------- | ---------- | ------------ |
| ❌         | ❌         | ❌           |

---

## 附录：写入标记速查表

下表汇总所有端点的 trace / audit / metrics 写入情况：

| 端点                                 | trace | audit | metrics |
| ------------------------------------ | ----- | ----- | ------- |
| `GET /health`                        | ❌    | ❌    | ❌      |
| `POST /tasks`                        | ✅    | ❌    | ✅      |
| `GET /tasks`                         | ❌    | ❌    | ❌      |
| `GET /tasks/{task_id}`               | ❌    | ❌    | ❌      |
| `GET /tasks/{task_id}/trace`         | ❌    | ❌    | ❌      |
| `POST /nl2sql/preview`               | ✅    | ❌    | ❌      |
| `POST /nl2sql/execute`               | ✅    | ❌    | ✅      |
| `POST /nl2sql/eval`                  | ✅    | ❌    | ❌      |
| `GET /tools`                         | ❌    | ❌    | ❌      |
| `POST /tools/{tool_name}/call`       | ✅    | ❌    | ✅      |
| `GET /approvals`                     | ❌    | ❌    | ❌      |
| `GET /approvals/summary`             | ❌    | ❌    | ❌      |
| `GET /approvals/{id}`                | ❌    | ❌    | ❌      |
| `GET /approvals/{id}/context`        | ❌    | ❌    | ❌      |
| `POST /approvals/{id}/approve`       | ✅    | ✅    | ❌      |
| `POST /approvals/{id}/reject`        | ✅    | ✅    | ❌      |
| `POST /approvals/{id}/resume`        | ✅    | ✅    | ❌      |
| `GET /audit/events`                  | ❌    | ❌    | ❌      |
| `GET /audit/events/{event_id}`       | ❌    | ❌    | ❌      |
| `GET /metrics/runtime`               | ❌    | ❌    | ❌      |
| `GET /metrics/cost/summary`          | ❌    | ❌    | ❌      |
| `GET /metrics/tools/summary`         | ❌    | ❌    | ❌      |
| `GET /metrics/tasks/summary`         | ❌    | ❌    | ❌      |
| `GET /runtime/snapshot`              | ❌    | ❌    | ❌      |
| `GET /eval/summary`                  | ❌    | ❌    | ❌      |
| `POST /eval/run-all`                 | ❌    | ❌    | ❌      |
| `POST /eval/bad-cases/run`           | ✅    | ❌    | ❌      |
| `GET /eval/bad-cases`                | ❌    | ❌    | ❌      |
| `POST /tasks/eval/multi-agent`       | ❌    | ❌    | ❌      |
| `GET /memory/{session_id}`           | ❌    | ❌    | ❌      |
| `DELETE /memory/{session_id}`        | ❌    | ❌    | ❌      |
| `GET /skills`                        | ❌    | ❌    | ❌      |
| `POST /skills/match`                 | ❌    | ❌    | ❌      |
| `POST /reflection/check`             | ❌    | ❌    | ❌      |

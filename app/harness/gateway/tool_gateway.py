from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

from app.models.schemas import ToolCallRecord, ToolCallStatus, ToolSpec


class ToolGateway:
    """工具网关

    统一管理本地工具和 MCP 远程工具的调用入口。
    v0.3 支持 local + MCP 工具统一注册/调用。
    v0.3.3 支持 retry_policy 重试。
    未注册工具、MCP 工具不存在、MCP 调用异常都返回 failed ToolCallRecord，不抛未处理异常。
    """

    def __init__(self) -> None:
        self._registry: dict[str, ToolSpec] = {}
        self._callables: dict[str, Any] = {}
        self._mcp_clients: dict[str, Any] = {}
        self._metrics_recorder: Any = None
        self._current_task_id: str = ""

    def set_metrics_recorder(self, recorder: Any) -> None:
        self._metrics_recorder = recorder

    def set_current_task_id(self, task_id: str) -> None:
        self._current_task_id = task_id

    def register(self, spec: ToolSpec, callable_fn: Any) -> None:
        self._registry[spec.tool_name] = spec
        self._callables[spec.tool_name] = callable_fn

    def register_mcp_server(self, server_name: str, client: Any) -> None:
        self._mcp_clients[server_name] = client

    def discover_mcp_tools(self, server_name: str) -> list[ToolSpec]:
        client = self._mcp_clients.get(server_name)
        if client is None:
            return []
        mcp_tools = client.list_tools()
        specs: list[ToolSpec] = []
        for tool_info in mcp_tools:
            spec = ToolSpec(
                tool_name=tool_info.name,
                description=tool_info.description,
                input_schema=tool_info.input_schema,
                output_schema=tool_info.output_schema,
                risk_level=tool_info.risk_level,
                permission_scope=tool_info.permission_scope,
                source="mcp",
                server_name=server_name,
                mcp_tool_name=tool_info.name,
                is_local=False,
            )
            self._registry[spec.tool_name] = spec
            self._callables[spec.tool_name] = None
            specs.append(spec)
        return specs

    def list_tools(self) -> list[ToolSpec]:
        return list(self._registry.values())

    def get_tool(self, tool_name: str) -> ToolSpec | None:
        return self._registry.get(tool_name)

    def call(self, tool_name: str, arguments: dict[str, Any] | None = None, task_id: str = "") -> ToolCallRecord:
        arguments = arguments or {}
        effective_task_id = task_id or self._current_task_id

        if tool_name not in self._registry:
            record = ToolCallRecord(
                call_id=str(uuid.uuid4()),
                tool_name=tool_name,
                arguments=arguments,
                status=ToolCallStatus.failed,
                success=False,
                error=f"工具 '{tool_name}' 未注册",
            )
            self._record_tool_metrics(tool_name, record, effective_task_id)
            return record

        spec = self._registry[tool_name]
        max_retries = spec.retry_policy.get("max_retries", 0)

        if spec.source == "mcp":
            record = self._call_mcp_with_retry(spec, arguments, max_retries)
        else:
            record = self._call_local_with_retry(tool_name, arguments, max_retries)

        self._record_tool_metrics(tool_name, record, effective_task_id)
        return record

    def _record_tool_metrics(self, tool_name: str, record: ToolCallRecord, task_id: str = "") -> None:
        if self._metrics_recorder is not None:
            try:
                self._metrics_recorder.record_tool_call(
                    tool_name=tool_name,
                    success=record.success,
                    latency_ms=record.latency_ms,
                    retry_count=record.retry_count,
                    task_id=task_id,
                )
            except Exception:
                pass

    def _call_local_with_retry(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        max_retries: int,
    ) -> ToolCallRecord:
        record = self._call_local(tool_name, arguments)
        retry_count = 0

        while not record.success and retry_count < max_retries:
            retry_count += 1
            record = self._call_local(tool_name, arguments)

        record.retry_count = retry_count
        return record

    def _call_local(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolCallRecord:
        record = ToolCallRecord(
            call_id=str(uuid.uuid4()),
            tool_name=tool_name,
            arguments=arguments,
            status=ToolCallStatus.running,
            called_at=datetime.now(),
        )

        callable_fn = self._callables.get(tool_name)
        if callable_fn is None:
            record.status = ToolCallStatus.failed
            record.success = False
            record.error = f"本地工具 '{tool_name}' 无可调用对象"
            record.result = None
            return record

        start = time.monotonic()
        try:
            result = callable_fn(**arguments)
            record.result = result
            if isinstance(result, dict) and result.get("error"):
                record.status = ToolCallStatus.failed
                record.success = False
                record.error = result["error"]
            else:
                record.status = ToolCallStatus.completed
                record.success = True
        except Exception as exc:
            record.result = None
            record.success = False
            record.status = ToolCallStatus.failed
            record.error = str(exc)
        finally:
            record.latency_ms = round((time.monotonic() - start) * 1000, 2)

        return record

    def _call_mcp_with_retry(
        self,
        spec: ToolSpec,
        arguments: dict[str, Any],
        max_retries: int,
    ) -> ToolCallRecord:
        record = self._call_mcp(spec, arguments)
        retry_count = 0

        while not record.success and retry_count < max_retries:
            retry_count += 1
            record = self._call_mcp(spec, arguments)

        record.retry_count = retry_count
        return record

    def _call_mcp(
        self,
        spec: ToolSpec,
        arguments: dict[str, Any],
    ) -> ToolCallRecord:
        record = ToolCallRecord(
            call_id=str(uuid.uuid4()),
            tool_name=spec.tool_name,
            arguments=arguments,
            status=ToolCallStatus.running,
            called_at=datetime.now(),
        )

        server_name = spec.server_name
        if server_name is None:
            record.status = ToolCallStatus.failed
            record.success = False
            record.error = f"MCP 工具 '{spec.tool_name}' 缺少 server_name"
            record.result = None
            return record

        client = self._mcp_clients.get(server_name)
        if client is None:
            record.status = ToolCallStatus.failed
            record.success = False
            record.error = f"MCP Server '{server_name}' 未注册"
            record.result = None
            return record

        start = time.monotonic()
        try:
            result = client.call_tool(spec.mcp_tool_name or spec.tool_name, arguments)
            record.result = result
            if isinstance(result, dict) and result.get("error"):
                record.status = ToolCallStatus.failed
                record.success = False
                record.error = result["error"]
            else:
                record.status = ToolCallStatus.completed
                record.success = True
        except Exception as exc:
            record.result = None
            record.success = False
            record.status = ToolCallStatus.failed
            record.error = str(exc)
        finally:
            record.latency_ms = round((time.monotonic() - start) * 1000, 2)

        return record

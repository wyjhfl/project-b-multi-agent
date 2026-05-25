from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import threading
from queue import Empty, Queue
from typing import Any, TextIO

from app.models.schemas import RiskLevel
from app.tools.mcp.client import MCPToolInfo

logger = logging.getLogger(__name__)


class MCPConfigError(RuntimeError):
    pass


class MCPProtocolError(RuntimeError):
    pass


class MCPTimeoutError(RuntimeError):
    pass


class MCPProcessCrashedError(RuntimeError):
    pass


class StdioMCPClient:
    def __init__(
        self,
        server_name: str,
        command: str = "",
        args: str = "",
        timeout_seconds: float = 10.0,
        workdir: str = "",
        env_allowlist: str = "",
        command_allowlist: str = "",
    ) -> None:
        self._server_name = server_name
        self._command = command.strip()
        self._args = args
        self._timeout_seconds = timeout_seconds
        self._workdir = workdir.strip()
        self._env_allowlist = env_allowlist
        self._command_allowlist = command_allowlist

        self._process: subprocess.Popen[str] | None = None
        self._started = False
        self._initialized = False
        self._request_id = 0

    @staticmethod
    def _parse_csv(value: str) -> list[str]:
        if not value:
            return []
        return [v.strip() for v in value.split(",") if v.strip()]

    def _build_env(self) -> dict[str, str]:
        allow = self._parse_csv(self._env_allowlist)
        if not allow:
            return dict(os.environ)
        env: dict[str, str] = {}
        for key in allow:
            if key in os.environ:
                env[key] = os.environ[key]
        return env

    def _ensure_configured(self) -> None:
        if not self._command:
            raise MCPConfigError(
                f"MCP Server '{self._server_name}' 未配置 command，请设置 MCP_SERVER_COMMAND"
            )
        allow = self._parse_csv(self._command_allowlist)
        if allow and self._command not in allow:
            raise MCPConfigError(
                f"MCP Server '{self._server_name}' command '{self._command}' 不在 allowlist 中"
            )

    def _build_cmdline(self) -> list[str]:
        parts = shlex.split(self._args, posix=True) if self._args else []
        return [self._command, *parts]

    def _start_process(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        cmdline = self._build_cmdline()
        self._process = subprocess.Popen(
            cmdline,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            shell=False,
            cwd=self._workdir or None,
            env=self._build_env(),
        )
        self._started = True
        self._initialized = False

    def _readline_with_timeout(self, stream: TextIO, timeout_seconds: float) -> str:
        q: Queue[str | None] = Queue(maxsize=1)

        def _reader() -> None:
            try:
                line = stream.readline()
            except Exception:
                line = None
            q.put(line)

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        try:
            line = q.get(timeout=timeout_seconds)
        except Empty as exc:
            raise MCPTimeoutError(f"MCP Server '{self._server_name}' 响应超时") from exc
        if line is None:
            raise MCPProtocolError(f"MCP Server '{self._server_name}' 无法读取响应")
        return line

    def _request(self, method: str, params: dict[str, Any]) -> Any:
        if self._process is None:
            raise MCPProcessCrashedError(f"MCP Server '{self._server_name}' 未启动")
        if self._process.poll() is not None:
            raise MCPProcessCrashedError(
                f"MCP Server '{self._server_name}' 进程已退出(exit={self._process.poll()})"
            )
        if self._process.stdin is None or self._process.stdout is None:
            raise MCPProtocolError(f"MCP Server '{self._server_name}' stdin/stdout 不可用")

        self._request_id += 1
        req_id = self._request_id
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        try:
            self._process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._process.stdin.flush()
        except OSError as exc:
            raise MCPProcessCrashedError(
                f"MCP Server '{self._server_name}' 写入失败，进程可能已崩溃"
            ) from exc

        line = self._readline_with_timeout(self._process.stdout, self._timeout_seconds).strip()
        if not line:
            raise MCPProtocolError(f"MCP Server '{self._server_name}' 返回空响应")
        try:
            resp = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MCPProtocolError(
                f"MCP Server '{self._server_name}' 返回非法 JSON: {line}"
            ) from exc

        if resp.get("jsonrpc") != "2.0":
            raise MCPProtocolError(f"MCP Server '{self._server_name}' JSON-RPC 版本非法")
        if resp.get("id") != req_id:
            raise MCPProtocolError(
                f"MCP Server '{self._server_name}' 响应 id 不匹配 expect={req_id} got={resp.get('id')}"
            )
        if "error" in resp and resp["error"] is not None:
            err = resp["error"]
            if isinstance(err, dict):
                msg = err.get("message", str(err))
            else:
                msg = str(err)
            raise MCPProtocolError(f"MCP Server '{self._server_name}' 返回错误: {msg}")
        if "result" not in resp:
            raise MCPProtocolError(f"MCP Server '{self._server_name}' 响应缺少 result")
        return resp["result"]

    def _initialize(self) -> None:
        result = self._request(
            "initialize",
            {
                "clientInfo": {"name": "project-b", "version": "2.1.0"},
                "capabilities": {},
            },
        )
        if not isinstance(result, dict):
            raise MCPProtocolError("initialize result 类型非法")
        self._initialized = True

    def _ensure_started(self) -> None:
        self._ensure_configured()
        if self._process is None or self._process.poll() is not None:
            self._start_process()
        if not self._initialized:
            self._initialize()

    @staticmethod
    def _normalize_risk_level(value: Any) -> RiskLevel:
        if isinstance(value, RiskLevel):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("low", "medium", "high"):
                return RiskLevel(normalized)
        return RiskLevel.medium

    @staticmethod
    def _normalize_permission_scope(value: Any) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "read"

    def _map_tool_item(self, item: Any) -> MCPToolInfo | None:
        if not isinstance(item, dict):
            logger.warning("MCP tool item 非法，已跳过: %r", item)
            return None
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            logger.warning("MCP tool item 缺少有效 name，已跳过: %r", item)
            return None
        description = item.get("description", "")
        input_schema = item.get("inputSchema")
        if input_schema is None:
            input_schema = item.get("input_schema")
        output_schema = item.get("outputSchema")
        if output_schema is None:
            output_schema = item.get("output_schema")
        risk_level = item.get("riskLevel")
        if risk_level is None:
            risk_level = item.get("risk_level")
        permission_scope = item.get("permissionScope")
        if permission_scope is None:
            permission_scope = item.get("permission_scope")
        return MCPToolInfo(
            name=name.strip(),
            description=description if isinstance(description, str) else str(description),
            input_schema=input_schema if isinstance(input_schema, dict) else {},
            output_schema=output_schema if isinstance(output_schema, dict) else {},
            risk_level=self._normalize_risk_level(risk_level),
            permission_scope=self._normalize_permission_scope(permission_scope),
        )

    def list_tools(self) -> list[MCPToolInfo]:
        try:
            self._ensure_started()
            result = self._request("tools/list", {})
        except (MCPConfigError, MCPProtocolError, MCPTimeoutError, MCPProcessCrashedError) as exc:
            logger.warning("StdioMCPClient.list_tools 失败: %s", exc)
            return []

        if isinstance(result, dict):
            raw_tools = result.get("tools", [])
        elif isinstance(result, list):
            raw_tools = result
        else:
            logger.warning("StdioMCPClient.list_tools result 非法: %r", result)
            return []

        if not isinstance(raw_tools, list):
            logger.warning("StdioMCPClient.list_tools tools 字段不是 list: %r", raw_tools)
            return []

        tools: list[MCPToolInfo] = []
        for item in raw_tools:
            mapped = self._map_tool_item(item)
            if mapped is not None:
                tools.append(mapped)
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            self._ensure_started()
        except (MCPConfigError, MCPProtocolError, MCPTimeoutError, MCPProcessCrashedError) as exc:
            return {"error": str(exc)}
        return {"error": f"MCP Server '{self._server_name}' 尚未实现 tools/call（Phase 3.3）"}

    def close(self) -> None:
        if self._process is None:
            self._started = False
            self._initialized = False
            return
        proc = self._process
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=min(1.0, max(0.2, self._timeout_seconds)))
                except Exception:
                    proc.kill()
                    proc.wait(timeout=1.0)
        except Exception:
            pass
        finally:
            for stream_name in ("stdin", "stdout", "stderr"):
                stream = getattr(proc, stream_name, None)
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
            self._process = None
            self._started = False
            self._initialized = False

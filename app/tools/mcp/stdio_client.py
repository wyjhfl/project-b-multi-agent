from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import threading
import tomllib
from importlib import metadata
from pathlib import Path
from queue import Empty, Queue
from typing import Any, TextIO

from app.models.schemas import RiskLevel
from app.tools.mcp.client import MCPToolInfo

logger = logging.getLogger(__name__)

MCP_STDERR_MAX_CHARS = 4000


def _resolve_client_version() -> str:
    try:
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "pyproject.toml"
            if not candidate.exists():
                continue
            data = tomllib.loads(candidate.read_text(encoding="utf-8"))
            version = data.get("project", {}).get("version")
            if isinstance(version, str) and version.strip():
                return version.strip()
    except Exception:
        pass
    try:
        return metadata.version("project-b-multi-agent")
    except Exception:
        return "3.6.0"


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
        self._lock = threading.RLock()

        self._last_error = ""
        self._request_count = 0
        self._failure_count = 0
        self._restart_count = 0
        self._last_restart_reason = ""

        self._stderr_buffer = ""
        self._stderr_thread: threading.Thread | None = None
        self._stderr_stop_event = threading.Event()
        self._client_version = _resolve_client_version()

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
                f"MCP server '{self._server_name}' missing command. Set MCP_SERVER_COMMAND."
            )
        allow = self._parse_csv(self._command_allowlist)
        if allow and self._command not in allow:
            raise MCPConfigError(
                f"MCP server '{self._server_name}' command '{self._command}' is not in allowlist."
            )

    def _build_cmdline(self) -> list[str]:
        parts = shlex.split(self._args, posix=True) if self._args else []
        return [self._command, *parts]

    def _append_stderr(self, chunk: str) -> None:
        if not chunk:
            return
        self._stderr_buffer = (self._stderr_buffer + chunk)[-MCP_STDERR_MAX_CHARS:]

    def _start_stderr_reader(self, process: subprocess.Popen[str]) -> None:
        stderr = process.stderr
        if stderr is None:
            return
        self._stderr_stop_event = threading.Event()

        def _reader() -> None:
            while not self._stderr_stop_event.is_set():
                try:
                    line = stderr.readline()
                except Exception:
                    break
                if not line:
                    break
                with self._lock:
                    self._append_stderr(line)

        self._stderr_thread = threading.Thread(target=_reader, daemon=True)
        self._stderr_thread.start()

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
        self._start_stderr_reader(self._process)
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
            raise MCPTimeoutError(f"MCP server '{self._server_name}' response timeout.") from exc
        if line is None:
            raise MCPProtocolError(f"MCP server '{self._server_name}' cannot read response.")
        return line

    def _request(self, method: str, params: dict[str, Any]) -> Any:
        if self._process is None:
            raise MCPProcessCrashedError(f"MCP server '{self._server_name}' is not started.")
        if self._process.poll() is not None:
            raise MCPProcessCrashedError(
                f"MCP server '{self._server_name}' exited (exit={self._process.poll()})."
            )
        if self._process.stdin is None or self._process.stdout is None:
            raise MCPProtocolError(f"MCP server '{self._server_name}' stdin/stdout is unavailable.")

        self._request_id += 1
        req_id = self._request_id
        self._request_count += 1
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
                f"MCP server '{self._server_name}' write failed."
            ) from exc

        line = self._readline_with_timeout(self._process.stdout, self._timeout_seconds).strip()
        if not line:
            raise MCPProtocolError(f"MCP server '{self._server_name}' returned empty response.")
        try:
            resp = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MCPProtocolError(
                f"MCP server '{self._server_name}' returned invalid JSON: {line}"
            ) from exc

        if resp.get("jsonrpc") != "2.0":
            raise MCPProtocolError(f"MCP server '{self._server_name}' invalid jsonrpc version.")
        if resp.get("id") != req_id:
            raise MCPProtocolError(
                f"MCP server '{self._server_name}' response id mismatch: expect={req_id}, got={resp.get('id')}."
            )
        if "error" in resp and resp["error"] is not None:
            err = resp["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise MCPProtocolError(f"MCP server '{self._server_name}' returned error: {msg}")
        if "result" not in resp:
            raise MCPProtocolError(f"MCP server '{self._server_name}' response missing result.")
        return resp["result"]

    def _initialize(self) -> None:
        result = self._request(
            "initialize",
            {
                "clientInfo": {"name": "project-b", "version": self._client_version},
                "capabilities": {},
            },
        )
        if not isinstance(result, dict):
            raise MCPProtocolError("Initialize result must be an object.")
        self._initialized = True

    def _cleanup_process(self, reason: str = "", terminate: bool = False) -> None:
        process = self._process
        self._stderr_stop_event.set()
        if process is not None:
            try:
                if terminate and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=min(1.0, max(0.2, self._timeout_seconds)))
                    except Exception:
                        process.kill()
                        process.wait(timeout=1.0)
            except Exception:
                pass
            finally:
                for stream_name in ("stdin", "stdout", "stderr"):
                    stream = getattr(process, stream_name, None)
                    if stream is not None:
                        try:
                            stream.close()
                        except Exception:
                            pass

        self._process = None
        self._started = False
        self._initialized = False
        if reason:
            self._last_restart_reason = reason

    def _format_error_with_stderr(self, message: str) -> str:
        if not self._stderr_buffer:
            return message
        stderr_tail = self._stderr_buffer[-MCP_STDERR_MAX_CHARS:].strip()
        if not stderr_tail:
            return message
        return f"{message} | stderr_tail={stderr_tail}"

    def _collect_stderr_if_available(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        if process.poll() is None:
            return
        try:
            chunk = process.stderr.read()
        except Exception:
            chunk = ""
        if chunk:
            self._append_stderr(chunk)

    def _record_failure(self, exc: Exception, restart_reason: str = "") -> str:
        self._failure_count += 1
        self._collect_stderr_if_available()
        error_message = self._format_error_with_stderr(str(exc))
        self._last_error = error_message
        if restart_reason:
            self._restart_count += 1
            self._cleanup_process(reason=restart_reason, terminate=True)
        return error_message

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
            logger.warning("MCP tool item invalid, skipped: %r", item)
            return None
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            logger.warning("MCP tool item missing valid name, skipped: %r", item)
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
        with self._lock:
            for attempt in range(2):
                try:
                    self._ensure_started()
                    result = self._request("tools/list", {})
                    break
                except MCPConfigError as exc:
                    self._record_failure(exc)
                    logger.warning("StdioMCPClient.list_tools failed: %s", exc)
                    return []
                except (MCPProtocolError, MCPTimeoutError, MCPProcessCrashedError) as exc:
                    error_message = self._record_failure(exc, restart_reason=type(exc).__name__)
                    logger.warning("StdioMCPClient.list_tools failed: %s", error_message)
                    if attempt == 0:
                        continue
                    return []
            else:
                return []

            if isinstance(result, dict):
                raw_tools = result.get("tools", [])
            elif isinstance(result, list):
                raw_tools = result
            else:
                self._last_error = f"Invalid tools/list result type: {type(result).__name__}"
                logger.warning("StdioMCPClient.list_tools result invalid: %r", result)
                return []

            if not isinstance(raw_tools, list):
                self._last_error = "Invalid tools/list payload: tools is not a list."
                logger.warning("StdioMCPClient.list_tools tools is not list: %r", raw_tools)
                return []

            tools: list[MCPToolInfo] = []
            for item in raw_tools:
                mapped = self._map_tool_item(item)
                if mapped is not None:
                    tools.append(mapped)
            return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            try:
                self._ensure_started()
                result = self._request(
                    "tools/call",
                    {
                        "name": name,
                        "arguments": arguments or {},
                    },
                )
            except MCPConfigError as exc:
                error_message = self._record_failure(exc)
                return {"error": error_message}
            except (MCPProtocolError, MCPTimeoutError, MCPProcessCrashedError) as exc:
                error_message = self._record_failure(exc, restart_reason=type(exc).__name__)
                return {"error": error_message}

            if isinstance(result, dict):
                return result
            return {"content": result}

    def get_health(self) -> dict[str, Any]:
        with self._lock:
            process_alive = self._process is not None and self._process.poll() is None
            pid = self._process.pid if self._process is not None else None
            return {
                "server_name": self._server_name,
                "started": self._started,
                "initialized": self._initialized,
                "process_alive": process_alive,
                "pid": pid,
                "last_error": self._last_error,
                "request_count": self._request_count,
                "failure_count": self._failure_count,
                "restart_count": self._restart_count,
                "last_restart_reason": self._last_restart_reason,
            }

    def health(self) -> dict[str, Any]:
        return self.get_health()

    def close(self) -> None:
        with self._lock:
            self._cleanup_process(reason="manual_close", terminate=True)

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import threading
from queue import Empty, Queue
from typing import Any

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
                f"MCP Server '{self._server_name}' 未配置 command，"
                f"请设置 MCP_SERVER_COMMAND 环境变量"
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

    def _readline_with_timeout(self, stream, timeout_seconds: float) -> str:
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

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
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
            raise MCPProtocolError(f"MCP Server '{self._server_name}' 返回非法 JSON: {line}") from exc

        if resp.get("jsonrpc") != "2.0":
            raise MCPProtocolError(f"MCP Server '{self._server_name}' JSON-RPC 版本不合法")
        if resp.get("id") != req_id:
            raise MCPProtocolError(
                f"MCP Server '{self._server_name}' 响应 id 不匹配: expect={req_id} got={resp.get('id')}"
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

    def list_tools(self) -> list[MCPToolInfo]:
        try:
            self._ensure_started()
        except (MCPConfigError, MCPProtocolError, MCPTimeoutError, MCPProcessCrashedError) as exc:
            logger.warning("StdioMCPClient.list_tools 失败: %s", exc)
            return []
        return []

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

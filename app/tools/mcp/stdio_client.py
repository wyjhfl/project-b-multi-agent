from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.mcp.client import MCPToolInfo

logger = logging.getLogger(__name__)


class MCPConfigError(RuntimeError):
    pass


class StdioMCPClient:
    def __init__(
        self,
        server_name: str,
        command: str = "",
        args: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._server_name = server_name
        self._command = command
        self._args = args
        self._timeout_seconds = timeout_seconds
        self._started = False

    def _ensure_configured(self) -> None:
        if not self._command:
            raise MCPConfigError(
                f"MCP Server '{self._server_name}' 未配置 command，"
                f"请设置 MCP_SERVER_COMMAND 环境变量"
            )

    def list_tools(self) -> list[MCPToolInfo]:
        try:
            self._ensure_configured()
        except MCPConfigError as exc:
            logger.warning("StdioMCPClient.list_tools 失败: %s", exc)
            return []
        logger.info(
            "StdioMCPClient.list_tools: server=%s command=%s (占位实现，返回空列表)",
            self._server_name,
            self._command,
        )
        return []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            self._ensure_configured()
        except MCPConfigError as exc:
            return {"error": str(exc)}
        logger.info(
            "StdioMCPClient.call_tool: server=%s tool=%s (占位实现)",
            self._server_name,
            name,
        )
        return {"error": f"MCP Server '{self._server_name}' 尚未实现真实协议调用"}

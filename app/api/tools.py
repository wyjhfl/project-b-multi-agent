from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.policy.engine import PolicyEngine
from app.models.schemas import RiskLevel, ToolCallRecord, ToolCallStatus, ToolSpec

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolInfoResponse(BaseModel):
    tool_name: str
    description: str
    source: str
    server_name: str | None = None
    risk_level: str
    permission_scope: str


class ToolCallRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    result: Any | None = None
    status: str
    success: bool
    latency_ms: float = 0.0
    error: str | None = None


def _get_gateway() -> ToolGateway:
    from app.main import get_gateway
    return get_gateway()


def _get_policy_engine() -> PolicyEngine:
    from app.main import get_policy_engine
    return get_policy_engine()


@router.get("", response_model=list[ToolInfoResponse])
async def list_tools():
    gateway = _get_gateway()
    tools = gateway.list_tools()
    return [
        ToolInfoResponse(
            tool_name=t.tool_name,
            description=t.description,
            source=t.source,
            server_name=t.server_name,
            risk_level=t.risk_level.value,
            permission_scope=t.permission_scope,
        )
        for t in tools
    ]


@router.post("/{tool_name}/call", response_model=ToolCallResponse)
async def call_tool(tool_name: str, req: ToolCallRequest):
    gateway = _get_gateway()
    policy_engine = _get_policy_engine()

    spec = gateway.get_tool(tool_name)
    if spec is None:
        record = ToolCallRecord(
            call_id=str(uuid.uuid4()),
            tool_name=tool_name,
            arguments=req.arguments,
            status=ToolCallStatus.failed,
            success=False,
            error=f"工具 '{tool_name}' 未注册",
            called_at=datetime.now(),
        )
        return ToolCallResponse(
            call_id=record.call_id,
            tool_name=record.tool_name,
            arguments=record.arguments,
            result=record.result,
            status=record.status.value,
            success=record.success,
            latency_ms=record.latency_ms,
            error=record.error,
        )

    decision = policy_engine.evaluate(tool_name, risk_level=spec.risk_level)
    if not decision["allowed"]:
        record = ToolCallRecord(
            call_id=str(uuid.uuid4()),
            tool_name=tool_name,
            arguments=req.arguments,
            status=ToolCallStatus.failed,
            success=False,
            error=decision["reason"],
            called_at=datetime.now(),
        )
        return ToolCallResponse(
            call_id=record.call_id,
            tool_name=record.tool_name,
            arguments=record.arguments,
            result=record.result,
            status=record.status.value,
            success=record.success,
            latency_ms=record.latency_ms,
            error=record.error,
        )

    record: ToolCallRecord = gateway.call(tool_name, req.arguments)
    return ToolCallResponse(
        call_id=record.call_id,
        tool_name=record.tool_name,
        arguments=record.arguments,
        result=record.result,
        status=record.status.value,
        success=record.success,
        latency_ms=record.latency_ms,
        error=record.error,
    )

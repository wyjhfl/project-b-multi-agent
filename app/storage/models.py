from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    user_id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    roles = Column(Text, nullable=False, default="")
    disabled = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())


class TaskRunRow(Base):
    __tablename__ = "task_runs"
    task_id = Column(String, primary_key=True)
    query = Column(Text, default="")
    mode = Column(String, default="")
    status = Column(String, default="")
    result_json = Column(Text, default=None)
    error = Column(Text, default=None)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ApprovalRequestRow(Base):
    __tablename__ = "approval_requests"
    approval_id = Column(String, primary_key=True)
    task_id = Column(String, default="")
    tool_name = Column(String, default="")
    action = Column(String, default="")
    risk_level = Column(String, default="")
    impact_scope = Column(String, default="")
    agent_reason = Column(Text, default="")
    status = Column(String, default="pending")
    requested_at = Column(DateTime, server_default=func.now())
    decided_at = Column(DateTime, default=None)
    decided_by = Column(String, default=None)
    decision_reason = Column(Text, default=None)
    payload_json = Column(Text, default=None)


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    actor = Column(String, nullable=False, default="system")
    task_id = Column(String, default=None)
    approval_id = Column(String, default=None)
    tool_name = Column(String, default=None)
    action = Column(String, nullable=False, default="")
    outcome = Column(String, nullable=False, default="success")
    reason = Column(Text, default=None)
    severity = Column(String, default=None)
    detail = Column(Text, nullable=False, default="{}")


class RuntimeTaskMetricRow(Base):
    __tablename__ = "runtime_task_metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, default="")
    mode = Column(String, default="")
    status = Column(String, default="")
    success = Column(Integer, default=0)
    latency_ms = Column(Float, default=0.0)
    timestamp = Column(DateTime, server_default=func.now())


class RuntimeToolMetricRow(Base):
    __tablename__ = "runtime_tool_metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, default="")
    tool_name = Column(String, default="")
    status = Column(String, default="")
    success = Column(Integer, default=0)
    latency_ms = Column(Float, default=0.0)
    retry_count = Column(Integer, default=0)
    timestamp = Column(DateTime, server_default=func.now())


class RuntimeTokenUsageRow(Base):
    __tablename__ = "runtime_token_usage"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, default="")
    model_name = Column(String, default="")
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    timestamp = Column(DateTime, server_default=func.now())

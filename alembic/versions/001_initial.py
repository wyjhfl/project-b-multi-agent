"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-05-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String, primary_key=True),
        sa.Column("username", sa.String, unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("roles", sa.Text, nullable=False, server_default=""),
        sa.Column("disabled", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "task_runs",
        sa.Column("task_id", sa.String, primary_key=True),
        sa.Column("query", sa.Text, server_default=""),
        sa.Column("mode", sa.String, server_default=""),
        sa.Column("status", sa.String, server_default=""),
        sa.Column("result_json", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "approval_requests",
        sa.Column("approval_id", sa.String, primary_key=True),
        sa.Column("task_id", sa.String, server_default=""),
        sa.Column("tool_name", sa.String, server_default=""),
        sa.Column("action", sa.String, server_default=""),
        sa.Column("risk_level", sa.String, server_default=""),
        sa.Column("impact_scope", sa.String, server_default=""),
        sa.Column("agent_reason", sa.Text, server_default=""),
        sa.Column("status", sa.String, server_default="pending"),
        sa.Column("requested_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime, nullable=True),
        sa.Column("decided_by", sa.String, nullable=True),
        sa.Column("decision_reason", sa.Text, nullable=True),
        sa.Column("payload_json", sa.Text, nullable=True),
    )
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String, primary_key=True),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("actor", sa.String, nullable=False, server_default="system"),
        sa.Column("task_id", sa.String, nullable=True),
        sa.Column("approval_id", sa.String, nullable=True),
        sa.Column("tool_name", sa.String, nullable=True),
        sa.Column("action", sa.String, nullable=False, server_default=""),
        sa.Column("outcome", sa.String, nullable=False, server_default="success"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("severity", sa.String, nullable=True),
        sa.Column("detail", sa.Text, nullable=False, server_default="{}"),
    )
    op.create_table(
        "runtime_task_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String, server_default=""),
        sa.Column("mode", sa.String, server_default=""),
        sa.Column("status", sa.String, server_default=""),
        sa.Column("success", sa.Integer, server_default="0"),
        sa.Column("latency_ms", sa.Float, server_default="0.0"),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "runtime_tool_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String, server_default=""),
        sa.Column("tool_name", sa.String, server_default=""),
        sa.Column("success", sa.Integer, server_default="0"),
        sa.Column("latency_ms", sa.Float, server_default="0.0"),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "runtime_token_usage",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String, server_default=""),
        sa.Column("model_name", sa.String, server_default=""),
        sa.Column("prompt_tokens", sa.Integer, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, server_default="0"),
        sa.Column("total_cost", sa.Float, server_default="0.0"),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("runtime_token_usage")
    op.drop_table("runtime_tool_metrics")
    op.drop_table("runtime_task_metrics")
    op.drop_table("audit_events")
    op.drop_table("approval_requests")
    op.drop_table("task_runs")
    op.drop_table("users")

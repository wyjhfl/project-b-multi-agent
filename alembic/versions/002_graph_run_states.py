"""graph run states

Revision ID: 002_graph_run_states
Revises: 001_initial
Create Date: 2026-05-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_graph_run_states"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "graph_run_states",
        sa.Column("checkpoint_id", sa.String, primary_key=True),
        sa.Column("task_id", sa.String, nullable=False),
        sa.Column("approval_id", sa.String, nullable=True),
        sa.Column("graph_thread_id", sa.String, nullable=True),
        sa.Column("run_id", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="running"),
        sa.Column("current_node", sa.String, nullable=True),
        sa.Column("graph_state", sa.JSON, nullable=False),
        sa.Column("pending_interrupt", sa.JSON, nullable=True),
        sa.Column("resume_payload", sa.JSON, nullable=True),
        sa.Column("result_snapshot", sa.JSON, nullable=True),
        sa.Column("consumed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("resumed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("resume_attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_resume_error", sa.Text, nullable=True),
        sa.Column("locked_by", sa.String, nullable=True),
        sa.Column("locked_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_graph_run_states_task_id", "graph_run_states", ["task_id"])
    op.create_index("ix_graph_run_states_approval_id", "graph_run_states", ["approval_id"])
    op.create_index("ix_graph_run_states_status_expires_at", "graph_run_states", ["status", "expires_at"])
    op.create_index("ix_graph_run_states_task_created_at", "graph_run_states", ["task_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_graph_run_states_task_created_at", table_name="graph_run_states")
    op.drop_index("ix_graph_run_states_status_expires_at", table_name="graph_run_states")
    op.drop_index("ix_graph_run_states_approval_id", table_name="graph_run_states")
    op.drop_index("ix_graph_run_states_task_id", table_name="graph_run_states")
    op.drop_table("graph_run_states")

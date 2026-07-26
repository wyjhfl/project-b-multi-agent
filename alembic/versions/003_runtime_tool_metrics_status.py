"""runtime_tool_metrics add status column

Revision ID: 003_runtime_tool_metrics_status
Revises: 002_graph_run_states
Create Date: 2026-07-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_runtime_tool_metrics_status"
down_revision: Union[str, None] = "002_graph_run_states"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "runtime_tool_metrics",
        sa.Column("status", sa.String, server_default=""),
    )


def downgrade() -> None:
    with op.batch_alter_table("runtime_tool_metrics") as batch_op:
        batch_op.drop_column("status")

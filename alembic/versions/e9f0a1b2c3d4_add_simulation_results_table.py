"""add_simulation_results_table

Revision ID: e9f0a1b2c3d4
Revises: 7cce8d1f124a
Create Date: 2026-04-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e9f0a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "7cce8d1f124a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "prediction_report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prediction_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("topic_context", sa.Text(), nullable=False),
        sa.Column("simulation_config", postgresql.JSONB(), nullable=False),
        sa.Column("results", postgresql.JSONB(), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
    )
    op.create_index(
        "ix_simulation_results_topic_context",
        "simulation_results",
        ["topic_context"],
    )
    op.create_index(
        "ix_simulation_results_generated_at",
        "simulation_results",
        ["generated_at"],
    )
    op.create_index(
        "ix_simulation_results_prediction_report_id",
        "simulation_results",
        ["prediction_report_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_simulation_results_prediction_report_id",
        table_name="simulation_results",
    )
    op.drop_index(
        "ix_simulation_results_generated_at",
        table_name="simulation_results",
    )
    op.drop_index(
        "ix_simulation_results_topic_context",
        table_name="simulation_results",
    )
    op.drop_table("simulation_results")

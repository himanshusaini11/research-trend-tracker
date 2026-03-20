"""add_prediction_reports_table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prediction_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("topic_context", sa.Text(), nullable=False),
        sa.Column("signals_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("report", postgresql.JSONB(), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_validated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("validation_notes", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_prediction_reports_topic_context",
        "prediction_reports",
        ["topic_context"],
    )
    op.create_index(
        "ix_prediction_reports_generated_at",
        "prediction_reports",
        ["generated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_prediction_reports_generated_at", table_name="prediction_reports")
    op.drop_index("ix_prediction_reports_topic_context", table_name="prediction_reports")
    op.drop_table("prediction_reports")

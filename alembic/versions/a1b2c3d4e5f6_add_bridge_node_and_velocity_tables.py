"""add_bridge_node_and_velocity_tables

Revision ID: a1b2c3d4e5f6
Revises: c8d2f3a91e4b
Create Date: 2026-03-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c8d2f3a91e4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create velocity_trend_enum ENUM type first
    op.execute("CREATE TYPE velocity_trend_enum AS ENUM ('accelerating', 'decelerating', 'stable');")

    op.create_table(
        "bridge_node_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("concept_name", sa.Text(), nullable=False),
        sa.Column("centrality_score", sa.Float(), nullable=False),
        sa.Column("graph_node_count", sa.Integer(), nullable=False),
        sa.Column("graph_edge_count", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("concept_name", name="uq_bridge_node_scores_concept_name"),
    )
    op.create_index("ix_bridge_node_scores_concept_name", "bridge_node_scores", ["concept_name"])

    op.create_table(
        "velocity_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("concept_name", sa.Text(), nullable=False),
        sa.Column("velocity", sa.Float(), nullable=False),
        sa.Column("acceleration", sa.Float(), nullable=False),
        sa.Column(
            "trend",
            sa.Enum("accelerating", "decelerating", "stable", name="velocity_trend_enum",
                    create_type=False),
            nullable=False,
        ),
        sa.Column("weeks_of_data", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("concept_name", name="uq_velocity_scores_concept_name"),
    )
    op.create_index("ix_velocity_scores_concept_name", "velocity_scores", ["concept_name"])


def downgrade() -> None:
    op.drop_index("ix_velocity_scores_concept_name", table_name="velocity_scores")
    op.drop_table("velocity_scores")
    op.drop_index("ix_bridge_node_scores_concept_name", table_name="bridge_node_scores")
    op.drop_table("bridge_node_scores")
    op.execute("DROP TYPE velocity_trend_enum;")

"""add_apache_age_extension

Revision ID: c8d2f3a91e4b
Revises: f3a9e1d07c52
Create Date: 2026-03-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c8d2f3a91e4b"
down_revision: Union[str, Sequence[str], None] = "f3a9e1d07c52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Install the AGE extension
    op.execute("CREATE EXTENSION IF NOT EXISTS age;")

    # 2. Load the AGE shared library and set search_path for this session
    op.execute("LOAD 'age';")
    op.execute('SET search_path = ag_catalog, "$user", public;')

    # 3. Create the graph — ag_catalog.create_graph has no IF NOT EXISTS,
    #    so guard with an existence check to keep the migration idempotent.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'research_graph'
            ) THEN
                PERFORM ag_catalog.create_graph('research_graph');
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("LOAD 'age';")
    op.execute('SET search_path = ag_catalog, "$user", public;')
    # drop_graph(name, cascade) — true drops all vertices/edges
    op.execute("SELECT * FROM ag_catalog.drop_graph('research_graph', true);")
    op.execute("DROP EXTENSION IF EXISTS age;")

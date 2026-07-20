"""Self-heal Apache AGE graph catalog OIDs after a pg_restore.

Why this exists:
    Apache AGE ties each graph's identity to a raw `oid` value —
    `ag_catalog.ag_graph.graphid` and `ag_catalog.ag_label.graph` are plain
    `oid` columns, not the OID-alias types (`regnamespace`, `regclass`) that
    pg_dump/pg_restore know how to re-resolve across a restore. Postgres
    assigns a *new* OID to the graph's schema on every restore into a fresh
    cluster, so these two catalog columns are left pointing at the old,
    dead OID from the source database. Result: all vertex/edge data
    restores intact, but every cypher() query fails with
    `graph with oid <N> does not exist` until these are patched.

    `ag_graph.namespace` (regnamespace) and `ag_label.relation` (regclass)
    *do* self-heal correctly across a restore — Postgres dumps them by
    name and re-resolves the current OID on load. This script uses those
    two self-healing columns as the source of truth to repair the two
    that don't.

Usage:
    uv run python scripts/restore_db.py

Idempotent: safe to run after every restore, or with nothing to fix — it
detects mismatches first and makes no changes if everything already
matches. Handles every AGE graph registered in the target database; no
graph name is hardcoded.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2

from app.core.config import settings


def _connect():
    return psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    )


def main() -> None:
    conn = _connect()
    conn.autocommit = True
    cur = conn.cursor()

    # AGE may not be installed at all (e.g. a non-graph restore) — bail out cleanly.
    cur.execute(
        "SELECT 1 FROM pg_extension WHERE extname = 'age';"
    )
    if cur.fetchone() is None:
        print("age extension not installed — nothing to do.")
        cur.close()
        conn.close()
        return

    cur.execute("LOAD 'age';")

    # --- Detect mismatches (read-only) -------------------------------------
    cur.execute(
        """
        SELECT name, graphid, namespace::oid
        FROM ag_catalog.ag_graph
        WHERE graphid <> namespace::oid;
        """
    )
    graph_mismatches = cur.fetchall()

    cur.execute(
        """
        SELECT l.name, l.graph, c.relnamespace
        FROM ag_catalog.ag_label l
        JOIN pg_class c ON c.oid = l.relation
        WHERE l.graph <> c.relnamespace;
        """
    )
    label_mismatches = cur.fetchall()

    if not graph_mismatches and not label_mismatches:
        print("AGE graph catalog already consistent — no action taken.")
        cur.close()
        conn.close()
        return

    print(f"Found {len(graph_mismatches)} ag_graph row(s) and "
          f"{len(label_mismatches)} ag_label row(s) with stale OIDs. Repairing...")
    for name, old, new in graph_mismatches:
        print(f"  ag_graph:  {name}: {old} -> {new}")
    for name, old, new in label_mismatches:
        print(f"  ag_label:  {name}: {old} -> {new}")

    # --- Repair, in one transaction ------------------------------------------
    # ag_label.graph has a non-deferrable FK to ag_graph.graphid, so both
    # sides must move together: drop the FK, fix both tables, put it back.
    conn.autocommit = False
    try:
        cur.execute(
            """
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'ag_catalog.ag_label'::regclass
              AND confrelid = 'ag_catalog.ag_graph'::regclass
              AND contype = 'f';
            """
        )
        fk_name, fk_def = cur.fetchone()

        cur.execute(f"ALTER TABLE ag_catalog.ag_label DROP CONSTRAINT {fk_name};")

        cur.execute(
            """
            UPDATE ag_catalog.ag_graph
            SET graphid = namespace::oid
            WHERE graphid <> namespace::oid;
            """
        )

        cur.execute(
            """
            UPDATE ag_catalog.ag_label AS l
            SET graph = c.relnamespace
            FROM pg_class c
            WHERE c.oid = l.relation
              AND l.graph <> c.relnamespace;
            """
        )

        cur.execute(f"ALTER TABLE ag_catalog.ag_label ADD CONSTRAINT {fk_name} {fk_def};")

        conn.commit()
        print("Repair committed.")
    except Exception:
        conn.rollback()
        print("Repair failed — rolled back, no changes made.")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

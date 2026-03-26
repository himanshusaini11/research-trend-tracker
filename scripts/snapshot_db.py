"""Take a pg_dump snapshot of key computed tables to snapshots/.

Usage:
    uv run python scripts/snapshot_db.py

Saves to /Volumes/MyProjects/Backup/research-trend-tracker/YYYYMMDD_HHMMSS.sql
"""
from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings

_TABLES = [
    "bridge_node_scores",
    "velocity_scores",
    "prediction_reports",
]

# keyword_counts: last 30 days only (too large to snapshot in full)
_KEYWORD_COUNTS_CONDITION = (
    "window_date >= NOW() - INTERVAL '30 days'"
)


def main() -> None:
    snapshots_dir = Path("/Volumes/MyProjects/Backup/research-trend-tracker")
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    output_file = snapshots_dir / f"{timestamp}.sql"

    # Build connection string components from settings
    host = settings.postgres_host
    port = settings.postgres_port
    user = settings.postgres_user
    db   = settings.postgres_db

    env = {"PGPASSWORD": settings.postgres_password}
    import os
    full_env = {**os.environ, **env}

    base_cmd = [
        "pg_dump",
        f"--host={host}",
        f"--port={port}",
        f"--username={user}",
        "--no-password",
        "--format=plain",
        "--encoding=UTF8",
    ]

    parts: list[str] = []

    # Full dump of the three computed tables
    for table in _TABLES:
        result = subprocess.run(
            base_cmd + [f"--table={table}", db],
            capture_output=True,
            text=True,
            env=full_env,
        )
        if result.returncode != 0:
            print(f"[warn] pg_dump failed for {table}: {result.stderr.strip()}")
        else:
            parts.append(result.stdout)

    # keyword_counts — last 30 days via --where
    result = subprocess.run(
        base_cmd + [
            "--table=keyword_counts",
            f"--where={_KEYWORD_COUNTS_CONDITION}",
            db,
        ],
        capture_output=True,
        text=True,
        env=full_env,
    )
    if result.returncode != 0:
        print(f"[warn] pg_dump failed for keyword_counts: {result.stderr.strip()}")
    else:
        parts.append(result.stdout)

    if not parts:
        print("No data dumped — check pg_dump errors above.")
        sys.exit(1)

    output_file.write_text("\n\n".join(parts), encoding="utf-8")
    size_kb = output_file.stat().st_size // 1024
    print(f"Snapshot saved: {output_file}  ({size_kb} KB)")


if __name__ == "__main__":
    main()

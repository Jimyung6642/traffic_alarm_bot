from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS commute_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_key TEXT,
    timestamp TEXT NOT NULL,
    origin_address TEXT,
    destination_address TEXT,
    transit_origin_address TEXT,
    transit_destination_address TEXT,
    current_drive_min REAL,
    current_transit_min REAL,
    baseline_min REAL,
    delay_min REAL,
    estimated_transit_min_low REAL,
    estimated_transit_min_high REAL,
    recommendation TEXT,
    reason TEXT,
    dry_run INTEGER NOT NULL,
    send_enabled INTEGER NOT NULL,
    message_sent INTEGER NOT NULL,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_commute_runs_run_key ON commute_runs(run_key);
CREATE INDEX IF NOT EXISTS idx_commute_runs_timestamp ON commute_runs(timestamp);
"""


def init_db(sqlite_path: str | Path) -> None:
    path = Path(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        with connection:
            connection.executescript(SCHEMA)
            _migrate_schema(connection)


def _migrate_schema(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(commute_runs)").fetchall()
    }
    migrations = {
        "transit_origin_address": "ALTER TABLE commute_runs ADD COLUMN transit_origin_address TEXT",
        "transit_destination_address": "ALTER TABLE commute_runs ADD COLUMN transit_destination_address TEXT",
        "current_transit_min": "ALTER TABLE commute_runs ADD COLUMN current_transit_min REAL",
    }
    for column_name, statement in migrations.items():
        if column_name not in existing_columns:
            connection.execute(statement)


def has_successful_message_for_run_key(sqlite_path: str | Path, run_key: str) -> bool:
    with closing(sqlite3.connect(sqlite_path)) as connection:
        row = connection.execute(
            "SELECT 1 FROM commute_runs WHERE run_key = ? AND message_sent = 1 LIMIT 1",
            (run_key,),
        ).fetchone()
    return row is not None


def record_run(sqlite_path: str | Path, **values: Any) -> None:
    fields = (
        "run_key",
        "timestamp",
        "origin_address",
        "destination_address",
        "transit_origin_address",
        "transit_destination_address",
        "current_drive_min",
        "current_transit_min",
        "baseline_min",
        "delay_min",
        "estimated_transit_min_low",
        "estimated_transit_min_high",
        "recommendation",
        "reason",
        "dry_run",
        "send_enabled",
        "message_sent",
        "error_message",
    )
    params = [values.get(field) for field in fields]
    params[14] = int(bool(params[14]))
    params[15] = int(bool(params[15]))
    params[16] = int(bool(params[16]))
    placeholders = ",".join("?" for _ in fields)
    with closing(sqlite3.connect(sqlite_path)) as connection:
        with connection:
            connection.execute(
                f"INSERT INTO commute_runs ({','.join(fields)}) VALUES ({placeholders})",
                params,
            )


def cleanup_old_records(sqlite_path: str | Path, *, retention_days: int, now: datetime) -> int:
    cutoff = now - timedelta(days=retention_days)
    with closing(sqlite3.connect(sqlite_path)) as connection:
        with connection:
            cursor = connection.execute(
                "DELETE FROM commute_runs WHERE timestamp < ?",
                (cutoff.isoformat(timespec="seconds"),),
            )
            return cursor.rowcount

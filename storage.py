from __future__ import annotations

import sqlite3
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
    current_drive_min REAL,
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
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)


def has_successful_message_for_run_key(sqlite_path: str | Path, run_key: str) -> bool:
    with sqlite3.connect(sqlite_path) as connection:
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
        "current_drive_min",
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
    params[11] = int(bool(params[11]))
    params[12] = int(bool(params[12]))
    params[13] = int(bool(params[13]))
    placeholders = ",".join("?" for _ in fields)
    with sqlite3.connect(sqlite_path) as connection:
        connection.execute(
            f"INSERT INTO commute_runs ({','.join(fields)}) VALUES ({placeholders})",
            params,
        )


def cleanup_old_records(sqlite_path: str | Path, *, retention_days: int, now: datetime) -> int:
    cutoff = now - timedelta(days=retention_days)
    with sqlite3.connect(sqlite_path) as connection:
        cursor = connection.execute(
            "DELETE FROM commute_runs WHERE timestamp < ?",
            (cutoff.isoformat(timespec="seconds"),),
        )
        return cursor.rowcount

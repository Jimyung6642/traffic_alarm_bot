from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from storage import cleanup_old_records, has_successful_message_for_run_key, init_db, record_run


class StorageTests(unittest.TestCase):
    def test_record_and_duplicate_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "history.sqlite3"
            init_db(db_path)

            record_run(
                db_path,
                run_key="scheduled:2026-05-20:06:00",
                timestamp="2026-05-20T06:00:00-04:00",
                dry_run=False,
                send_enabled=True,
                message_sent=True,
            )

            self.assertTrue(has_successful_message_for_run_key(db_path, "scheduled:2026-05-20:06:00"))

    def test_cleanup_old_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "history.sqlite3"
            init_db(db_path)
            now = datetime(2026, 5, 20, 8, 0, tzinfo=ZoneInfo("America/New_York"))
            old = now - timedelta(days=9)

            record_run(
                db_path,
                run_key="old",
                timestamp=old.isoformat(timespec="seconds"),
                dry_run=True,
                send_enabled=False,
                message_sent=False,
            )
            record_run(
                db_path,
                run_key="new",
                timestamp=now.isoformat(timespec="seconds"),
                dry_run=True,
                send_enabled=False,
                message_sent=False,
            )

            deleted = cleanup_old_records(db_path, retention_days=7, now=now)

            self.assertEqual(deleted, 1)
            with closing(sqlite3.connect(db_path)) as connection:
                rows = connection.execute("SELECT run_key FROM commute_runs").fetchall()
            self.assertEqual(rows, [("new",)])

    def test_init_db_migrates_existing_history_with_transit_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "history.sqlite3"
            with closing(sqlite3.connect(db_path)) as connection:
                with connection:
                    connection.execute(
                        """
                        CREATE TABLE commute_runs (
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
                        )
                        """
                    )

            init_db(db_path)

            with closing(sqlite3.connect(db_path)) as connection:
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(commute_runs)").fetchall()
                }
            self.assertIn("transit_origin_address", columns)
            self.assertIn("transit_destination_address", columns)
            self.assertIn("current_transit_min", columns)


if __name__ == "__main__":
    unittest.main()

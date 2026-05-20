from __future__ import annotations

import sqlite3
import tempfile
import unittest
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
            with sqlite3.connect(db_path) as connection:
                rows = connection.execute("SELECT run_key FROM commute_runs").fetchall()
            self.assertEqual(rows, [("new",)])


if __name__ == "__main__":
    unittest.main()

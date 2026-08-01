from pathlib import Path
from contextlib import closing
import sqlite3
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.web.db import WebConsoleDb


class WebConsoleDbTests(unittest.TestCase):
    def test_record_request_inserts_request_history(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "console.sqlite3"
            db = WebConsoleDb(db_path)

            db.record_request("GET", "/api/health", 200)

            with closing(sqlite3.connect(db_path)) as connection:
                rows = connection.execute(
                    "select method, path, status_code from request_history"
                ).fetchall()
            self.assertEqual(rows, [("GET", "/api/health", 200)])

    def test_initialize_creates_only_console_metadata_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "console.sqlite3"

            WebConsoleDb(db_path)

            with closing(sqlite3.connect(db_path)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "select name from sqlite_master where type = 'table'"
                    ).fetchall()
                }
            self.assertEqual(tables, {"request_history"})


if __name__ == "__main__":
    unittest.main()

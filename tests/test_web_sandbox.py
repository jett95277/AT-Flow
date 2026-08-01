from pathlib import Path
import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient

from at_flow.web.app import create_app
from at_flow.workspace import ATWorkspace


class WebSandboxTests(unittest.TestCase):
    def test_file_endpoint_rejects_traversal_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            traversal = client.get("/api/file", params={"path": "../at.config.json"})
            absolute = client.get("/api/file", params={"path": str(workspace.root / "at.config.json")})

            self.assertEqual(traversal.status_code, 403)
            self.assertEqual(absolute.status_code, 403)
            self.assertEqual(traversal.json()["error"]["code"], "file_not_allowed")
            self.assertEqual(absolute.json()["error"]["code"], "file_not_allowed")

    def test_api_does_not_expose_file_write_delete_upload_or_shell_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))
            routes = {
                (method, route.path)
                for route in client.app.routes
                for method in getattr(route, "methods", set())
            }

            forbidden_fragments = ("delete", "upload", "shell", "exec", "write")
            for _method, path in routes:
                self.assertFalse(any(fragment in path.lower() for fragment in forbidden_fragments), path)

    def test_sqlite_contains_console_metadata_only_after_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ATWorkspace.init(root)
            client = TestClient(create_app(root))

            client.get("/api/health")

            db_path = root / ".at" / "web" / "console.sqlite3"
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

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.registry import (
    create_session,
    create_task,
    get_session,
    list_sessions,
    update_session_status,
)
from at_runtime.workspace import initialize_workspace


class RegistryTests(unittest.TestCase):
    def test_create_task_and_session(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            task = create_task(root, "T17", "fix beam stability", {"project": "ASR-Agent"})
            session = create_session(root, "analysis-T17-01", "T17", "analysis", "codex")
            self.assertEqual(session["task_id"], "T17")
            self.assertEqual(session["status"], "created")
            self.assertEqual(get_session(root, "analysis-T17-01")["role"], "analysis")
            self.assertEqual(len(list_sessions(root)), 1)
            updated = update_session_status(root, "analysis-T17-01", "running")
            self.assertEqual(updated["status"], "running")


if __name__ == "__main__":
    unittest.main()

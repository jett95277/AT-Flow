"""M5a tests: orchestration timeline (checkpoint workspace+memory / list / rollback)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot import commands, timeline, workspace
from xiaot_memory.workspace import initialize_workspace


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        initialize_workspace(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_checkpoint_captures_workspace_and_lists(self):
        r = commands.task("some work", project="P", root=self.root)
        task_id = r["task_id"]
        # mutate workspace after checkpoint to verify rollback restores
        (workspace.workspace_dir(self.root, task_id) / "extra.txt").write_text("x", encoding="utf-8")
        node = timeline.checkpoint(self.root, task_id, label="milestone-1")
        self.assertTrue(node["id"].endswith("milestone-1"))
        nodes = timeline.list_nodes(self.root)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["task_id"], task_id)

    def test_rollback_restores_workspace(self):
        r = commands.task("work A", project="P", root=self.root)
        task_id = r["task_id"]
        plan_path = workspace.workspace_dir(self.root, task_id) / "plan.md"
        before = plan_path.read_text(encoding="utf-8")
        node = timeline.checkpoint(self.root, task_id, label="save")
        # corrupt workspace after snapshot
        plan_path.write_text("CORRUPTED", encoding="utf-8")
        res = timeline.rollback(self.root, node["id"])
        self.assertTrue(res["ok"])
        after = plan_path.read_text(encoding="utf-8")
        self.assertEqual(after, before)

    def test_rollback_unknown_node_fails(self):
        res = timeline.rollback(self.root, "task-nope-20200101T000000-x")
        self.assertFalse(res["ok"])


if __name__ == "__main__":
    unittest.main()

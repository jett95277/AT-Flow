"""M1 tests: models + workspace + memory_service + core commands closed loop."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot import commands, memory_service, workspace
from xiaot.models import ContextPack, RuntimeStatus, Task


class ModelsTests(unittest.TestCase):
    def test_task_carries_ownership(self):
        t = Task(id="t1", prompt="do x", project="p")
        self.assertEqual(t.project, "p")
        self.assertFalse(hasattr(t, "memory"))

    def test_result_statuses(self):
        self.assertEqual(RuntimeStatus("cancelled"), RuntimeStatus.CANCELLED)

    def test_contextpack_defaults(self):
        c = ContextPack(task=Task(id="t1", prompt="x"))
        self.assertEqual(c.constraints, [])
        self.assertIsNone(c.spec)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_plan_and_result_persist(self):
        w = workspace.write_plan(self.root, "t1", {"title": "T", "goal": "g",
                                                   "steps": ["a", "b"],
                                                   "acceptance": "ok"})
        self.assertTrue(w.exists())
        self.assertTrue((workspace.workspace_dir(self.root, "t1") / "plan.json").exists())
        workspace.write_result(self.root, "t1", "success", "done")
        self.assertTrue((workspace.workspace_dir(self.root, "t1") / "result.md").exists())

    def test_workspace_is_resume_source(self):
        commands.task("some task", project="P", root=self.root)
        # after task, a workspace exists
        task_id = workspace.list_workspaces(self.root)[0]
        state = workspace.read_workspace(self.root, task_id)
        self.assertEqual(state["task_id"], task_id)
        self.assertIn("plan", state)


class MemoryServiceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_retrieve_empty_memory_ok(self):
        r = memory_service.retrieve(self.root, {"id": "t1", "project": None})
        self.assertFalse(r["present"])
        self.assertEqual(r["summary"], [])

    def test_settle_returns_manual_suggestions(self):
        workspace.write_result(self.root, "t1", "success", "done")
        s = memory_service.suggest_settle(self.root, "t1")
        self.assertEqual(s["policy"], "all_promotions_manual")
        self.assertTrue(s["suggestions"])


class CommandTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_task_closed_loop(self):
        r = commands.task("重构记忆模块", project="demo", root=self.root)
        self.assertTrue(r["ok"])
        self.assertIn("task_id", r)
        self.assertTrue(r["workspace"].endswith(r["task_id"]))
        # context fragment contains memory summary shape
        self.assertIn("memory_summary", r["context"])

    def test_task_resume_unknown_fails(self):
        r = commands.task("x", resume="task-nope", root=self.root)
        self.assertFalse(r["ok"])

    def test_plan_and_settle(self):
        p = commands.plan("do thing", project="P", root=self.root)
        self.assertIn("task_id", p)
        s = commands.settle(p["task_id"], status="success", output="done", root=self.root)
        self.assertEqual(s["status"], "success")


if __name__ == "__main__":
    unittest.main()

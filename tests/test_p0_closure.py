"""P0 tests: init command, setup shell presence, settle->confirm->inject closure.

The memory loop must actually turn: settle proposes -> human confirms (confirm)
writes into medium -> a later task's retrieve injects that conclusion back.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot import commands, memory_service
from xiaot_memory.memory import read_memory
from xiaot_memory.workspace import initialize_workspace


def _mkroot() -> Path:
    d = Path(tempfile.mkdtemp())
    initialize_workspace(d)
    return d


class InitCommandTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_init_creates_workspace_and_injects(self):
        r = commands.init(project_root=self.root)
        self.assertTrue(r["ok"])
        self.assertTrue((self.root / ".xiaot/workspace").exists())
        self.assertTrue((self.root / ".opencode/skills/xiaot-orchestrate/SKILL.md").exists())

    def test_init_missing_dir_fails(self):
        r = commands.init(project_root=self.root / "nope")
        self.assertFalse(r["ok"])


class ConfirmWriteTests(unittest.TestCase):
    def setUp(self):
        self.root = _mkroot()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_confirm_project_scope_writes(self):
        r = commands.confirm("项目统一用 FastAPI", scope="project",
                             project="demo", evidence="seen in all modules",
                             root=self.root)
        self.assertTrue(r["ok"])
        got = read_memory(self.root, "memory://project/demo/medium")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["source"].get("project"), "demo")
        self.assertIn("evidence", got[0]["source"])

    def test_confirm_requires_scope_fields(self):
        r = commands.confirm("x", scope="project", root=self.root)
        self.assertFalse(r["ok"])

    def test_memory_loop_turns(self):
        # settle proposes -> confirm writes -> next task retrieve injects it
        t = commands.task("first task on topic demo-x", root=self.root)
        commands.settle(t["task_id"], status="success", output="done",
                        candidates=[{"text": "demo-x 结论：用 FastAPI",
                                     "scope": "project"}],
                        root=self.root)
        # human approves -> write to project scope
        commands.confirm("demo-x 结论：用 FastAPI", scope="project",
                         project="proj-demo", root=self.root)
        # a later task on same project retrieves it
        r2 = commands.task("继续 demo-x", project="proj-demo", root=self.root)
        summaries = " ".join(s["summary"] for s in r2["memory"]["summary"])
        self.assertIn("FastAPI", summaries)


if __name__ == "__main__":
    unittest.main()

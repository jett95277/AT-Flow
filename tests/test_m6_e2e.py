"""M6 E2E: three chains (plain task / spec task / memory lifecycle).

Plain: task -> retrieve -> context -> (mock agent report) -> settle.
Spec: large task flags needs_spec; spec CLI (when available) drives a real
      work unit whose artifact path feeds the context (reuse, not re-implement).
Lifecycle: settle suggestions -> manual confirm -> medium write (A model).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot import commands, spec_adapter, spec_router, workspace
from xiaot_memory.memory import read_memory, write_memory_structured
from xiaot_memory.workspace import initialize_workspace


def _mkroot() -> Path:
    d = Path(tempfile.mkdtemp())
    initialize_workspace(d)
    return d


class PlainTaskChainTests(unittest.TestCase):
    def setUp(self):
        self.root = _mkroot()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_plain_chain(self):
        # seed memory so injection is meaningful
        write_memory_structured(self.root, "memory://task/topic-x/medium",
                                conclusion="已确认：模块用 FastAPI",
                                source={"project": "P"})
        r = commands.task("继续 topic-x 开发", project="P", root=self.root)
        self.assertTrue(r["ok"])
        self.assertFalse(r["spec"]["needs_spec"])
        self.assertIn("memory_summary", r["context"])
        # mock agent report -> settle
        s = commands.settle(r["task_id"], status="success", output="did the work",
                            candidates=[{"text": "topic-x 新增结论", "scope": "task"}],
                            root=self.root)
        self.assertEqual(s["status"], "success")
        self.assertEqual(s["suggestions"][0]["action"], "review")


class SpecTaskChainTests(unittest.TestCase):
    def setUp(self):
        self.root = _mkroot()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_large_task_flags_spec(self):
        r = commands.task("实现一个新的订单导出功能", project="P", root=self.root)
        self.assertTrue(r["ok"])  # CLI available -> not blocked
        self.assertTrue(r["spec"]["needs_spec"])
        self.assertEqual(r["spec"]["scale"], "large")

    @unittest.skipUnless(spec_adapter.available(), "spec CLI unavailable")
    def test_spec_adapter_real_work_unit(self):
        # real reuse: init a spec workspace in temp, drive new change + status
        spec_dir = Path(tempfile.mkdtemp())
        init = spec_adapter.init_workspace(spec_dir)
        self.assertTrue(init["ok"], init.get("stderr", ""))
        nc = spec_adapter.new_change("e2e-spec-task", cwd=spec_dir)
        self.assertTrue(nc["ok"], nc.get("stderr", ""))
        st = spec_adapter.status_json("e2e-spec-task", cwd=spec_dir)
        self.assertTrue(st["ok"])
        self.assertIn("artifactPaths", st.get("stdout", ""))
        shutil.rmtree(spec_dir, ignore_errors=True)


class MemoryLifecycleChainTests(unittest.TestCase):
    def setUp(self):
        self.root = _mkroot()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_settle_then_manual_medium_write(self):
        # settle produces suggestions; human confirm -> project scope write
        workspace.write_result(self.root, "t9", "success", "done")
        from xiaot import memory_service
        s = memory_service.suggest_settle(
            self.root, "t9",
            candidates=[{"text": "项目级事实：统一用 FastAPI", "scope": "project"}])
        self.assertEqual(s["suggestions"][0]["scope"], "project")
        # human confirm -> write to project scope (A model: medium/project)
        write_memory_structured(self.root, "memory://project/P/medium",
                                conclusion="项目级事实：统一用 FastAPI",
                                source={"project": "P"})
        got = read_memory(self.root, "memory://project/P/medium")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["content"], "项目级事实：统一用 FastAPI")


if __name__ == "__main__":
    unittest.main()

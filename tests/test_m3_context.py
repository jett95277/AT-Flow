"""M3 tests: context fragment assembly (reference-style injection).

Context fragment carries instruction + bounded memory summary + refs +
skill hints + spec decision. Inline content is bounded; over-budget memory
is reported via refs for read-by-reference, never dumped in full.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot import commands
from xiaot.models import Task
from xiaot_memory.memory import write_memory_structured
from xiaot_memory.workspace import initialize_workspace


def _mkroot() -> Path:
    d = Path(tempfile.mkdtemp())
    initialize_workspace(d)
    return d


def _ctx(memory: dict | None = None, skills=None, spec=None):
    t = Task(id="t1", prompt="重构记忆模块", project="P")
    return commands.build_context(
        t, memory or {"present": False, "summary": [], "refs": {"total": 0,
                                                                "inline": 0, "uris": []}},
        skill_hints=skills, spec_decision=spec)


class ContextAssemblyTests(unittest.TestCase):
    def test_fragment_shape(self):
        c = _ctx()
        for key in ("task_id", "instruction", "memory_present", "memory_summary",
                    "memory_refs", "skill_hints", "spec_decision", "constraints"):
            self.assertIn(key, c)

    def test_memory_inline_bounded_and_refs(self):
        # simulate memory service output with more entries than budget
        mem = {
            "present": True,
            "summary": [{"uri": f"memory://task/x{i}/medium", "summary": f"s{i}"}
                        for i in range(5)],
            "refs": {"total": 12, "inline": 5, "uris": ["memory://task/x/medium"]},
        }
        c = _ctx(memory=mem)
        self.assertEqual(len(c["memory_summary"]), 5)     # inline bounded
        self.assertEqual(c["memory_refs"]["total"], 12)   # over-budget via refs
        self.assertTrue(c["memory_refs"]["uris"])

    def test_skill_and_spec_fields(self):
        c = _ctx(skills=[{"name": "code-simplification"}],
                 spec={"needs_spec": False})
        self.assertEqual(c["skill_hints"][0]["name"], "code-simplification")
        self.assertFalse(c["spec_decision"]["needs_spec"])

    def test_instruction_carries_task(self):
        c = _ctx()
        self.assertIn("重构记忆模块", c["instruction"])


class ContextViaRetrieveTests(unittest.TestCase):
    """Real task -> retrieve -> context: over-budget memory never dumped."""

    def setUp(self):
        self.root = _mkroot()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def test_task_context_has_refs_not_dump(self):
        # seed many entries under one topic to exceed a small budget
        for i in range(10):
            write_memory_structured(self.root, f"memory://task/topic-x/medium",
                                    conclusion=f"conclusion {i}",
                                    source={"project": "P"})
        r = commands.task("改 topic-x", project="P", root=self.root)
        self.assertTrue(r["ok"])
        ctx = r["context"]
        # inline summary limited; refs carry the full picture for read-by-ref
        self.assertLessEqual(len(ctx["memory_summary"]), 5)
        self.assertIn("memory_refs", ctx)


if __name__ == "__main__":
    unittest.main()

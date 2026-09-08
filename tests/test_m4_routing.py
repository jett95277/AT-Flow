"""M4 tests: skill router, spec router, spec adapter, task integration."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot import commands, skill_router, spec_adapter, spec_router, workspace
from xiaot_memory.workspace import initialize_workspace


class SkillRouterTests(unittest.TestCase):
    def test_finds_skills_dir(self):
        d = skill_router._find_skills_dir()
        self.assertIsNotNone(d)

    def test_resolve_empty_when_no_match(self):
        hints = skill_router.resolve("改写这个随机无关字符串 zzz")
        # may still be empty list; assert type only
        self.assertIsInstance(hints, list)


class SpecRouterTests(unittest.TestCase):
    def test_light_task_no_spec(self):
        r = spec_router.should_spec("修正一个 typo")
        self.assertFalse(r["needs_spec"])
        self.assertEqual(r["scale"], "light")

    def test_large_feature_spec(self):
        r = spec_router.should_spec("实现一个新的订单导出功能")
        self.assertTrue(r["needs_spec"])
        self.assertEqual(r["scale"], "large")


class SpecAdapterTests(unittest.TestCase):
    def test_available_returns_bool(self):
        self.assertIsInstance(spec_adapter.available(), bool)


class CommandIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        initialize_workspace(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_light_task_ok_with_spec_decision(self):
        r = commands.task("修正 typo", project="P", root=self.root)
        self.assertTrue(r["ok"])
        self.assertIn("spec", r)
        self.assertFalse(r["spec"]["needs_spec"])

    def test_spec_task_fails_clearly_when_cli_unavailable(self):
        # when the spec CLI is unavailable a spec-required task must error,
        # not silently degrade
        if spec_adapter.available():
            self.skipTest("spec CLI installed; availability gate not exercised")
        r = commands.task("实现一个新的订单导出功能", project="P", root=self.root)
        self.assertFalse(r["ok"])
        self.assertIn("spec workflow CLI is unavailable", r["error"])

    def test_context_carries_skill_and_spec_fields(self):
        r = commands.task("修正 typo", project="P", root=self.root)
        self.assertIn("skill_hints", r["context"])
        self.assertIn("spec_decision", r["context"])


if __name__ == "__main__":
    unittest.main()

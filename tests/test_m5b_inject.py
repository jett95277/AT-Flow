"""M5b tests: agent injection generation (commands + driver skill)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot import inject


class InjectTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_generates_command_files(self):
        res = inject.generate(self.root, agent="opencode")
        self.assertTrue(res["ok"])
        for name in inject.CORE_COMMANDS:
            f = self.root / ".opencode" / "commands" / f"xiaot-{name}.md"
            self.assertTrue(f.exists(), f"{name} command missing")

    def test_command_has_frontmatter_and_cli_guidance(self):
        inject.generate(self.root)
        task_cmd = (self.root / ".opencode/commands/xiaot-task.md").read_text(encoding="utf-8")
        self.assertIn("description:", task_cmd)
        self.assertIn("xiaot task", task_cmd)

    def test_driver_skill_generated(self):
        inject.generate(self.root)
        skill = self.root / ".opencode/skills/xiaot-orchestrate/SKILL.md"
        self.assertTrue(skill.exists())
        body = skill.read_text(encoding="utf-8")
        self.assertIn("xiaot task", body)
        self.assertIn("settle", body)
        self.assertIn("allowed-tools: Bash(xiaot:*)", body)

    def test_agent_dir_custom(self):
        res = inject.generate(self.root, agent="codex")
        self.assertTrue((self.root / ".codex/commands/xiaot-task.md").exists())
        self.assertIn(".codex/commands", res["files"][0])


if __name__ == "__main__":
    unittest.main()

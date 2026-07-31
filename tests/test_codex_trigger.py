from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.codex_trigger import install_codex_trigger
from at_flow.cli import main


class CodexTriggerTests(unittest.TestCase):
    def test_install_codex_trigger_creates_agents_md(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            at_entrypoint = target / "at.py"

            path = install_codex_trigger(target, at_entrypoint)
            content = path.read_text(encoding="utf-8")

            self.assertEqual(path.name, "AGENTS.md")
            self.assertIn("AT Flow Trigger", content)
            self.assertIn("`AT`", content)
            self.assertIn("`AT:`", content)
            self.assertIn("`AT：`", content)
            self.assertIn("panel --format chat", content)
            self.assertIn(f'python "{at_entrypoint.resolve()}"', content)

    def test_install_codex_trigger_defaults_to_module_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)

            path = install_codex_trigger(target)
            content = path.read_text(encoding="utf-8")

            self.assertIn("python -m at_flow --root", content)
            self.assertIn("panel --format chat", content)

    def test_install_codex_trigger_preserves_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            agents = target / "AGENTS.md"
            agents.write_text("# Existing\n\nKeep this.\n", encoding="utf-8")

            install_codex_trigger(target, target / "at.py")
            first = agents.read_text(encoding="utf-8")
            install_codex_trigger(target, target / "at.py")
            second = agents.read_text(encoding="utf-8")

            self.assertIn("Keep this.", second)
            self.assertEqual(first, second)
            self.assertEqual(second.count("AT_FLOW_TRIGGER_BEGIN"), 1)

    def test_enable_command_initializes_workspace_and_installs_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)

            exit_code = main(["enable", "--target", str(target)])

            self.assertEqual(exit_code, 0)
            self.assertTrue((target / "at.config.json").exists())
            self.assertTrue((target / ".at" / "shared" / "agents" / "main" / "agent.md").exists())
            content = (target / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("python -m at_flow --root", content)


if __name__ == "__main__":
    unittest.main()

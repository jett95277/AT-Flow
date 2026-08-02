from pathlib import Path
import json
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.migrations import MigrationError, migrate_agent_layout
from at_flow.workspace import ATWorkspace


class AgentLayoutMigrationTests(unittest.TestCase):
    def test_fresh_workspace_puts_agent_definitions_outside_shared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            workspace = ATWorkspace.init(root)

            self.assertEqual(workspace.agents_root, (root / ".at" / "agents").resolve())
            self.assertTrue((root / ".at" / "agents" / "main" / "agent.md").exists())
            self.assertFalse((root / ".at" / "shared" / "agents").exists())

    def test_migration_preview_does_not_change_legacy_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._legacy_workspace(Path(directory))

            result = migrate_agent_layout(root, apply=False)

            self.assertEqual(result.status, "preview")
            self.assertTrue((root / ".at" / "shared" / "agents" / "main" / "agent.md").exists())
            config = json.loads((root / "at.config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["workspace"]["agents_dir"], ".at/shared/agents")

    def test_migration_moves_packages_and_updates_only_agent_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._legacy_workspace(Path(directory))
            config_path = root / "at.config.json"
            original = json.loads(config_path.read_text(encoding="utf-8"))
            original["custom"] = {"preserve": True}
            config_path.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")

            result = migrate_agent_layout(root, apply=True)

            self.assertEqual(result.status, "migrated")
            self.assertIn("main/agent.md", result.moved_files)
            self.assertFalse((root / ".at" / "shared" / "agents").exists())
            self.assertTrue((root / ".at" / "agents" / "main" / "agent.md").exists())
            updated = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["workspace"]["agents_dir"], ".at/agents")
            self.assertEqual(updated["custom"], {"preserve": True})

    def test_migration_refuses_non_empty_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._legacy_workspace(Path(directory))
            target = root / ".at" / "agents"
            target.mkdir(parents=True)
            (target / "existing.txt").write_text("keep", encoding="utf-8")

            with self.assertRaises(MigrationError):
                migrate_agent_layout(root, apply=True)

            self.assertTrue((root / ".at" / "shared" / "agents" / "main" / "agent.md").exists())
            self.assertEqual((target / "existing.txt").read_text(encoding="utf-8"), "keep")

    def _legacy_workspace(self, root: Path) -> Path:
        workspace = ATWorkspace.init(root)
        current = workspace.agents_root
        legacy = root / ".at" / "shared" / "agents"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        current.rename(legacy)
        config_path = root / "at.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["workspace"]["agents_dir"] = ".at/shared/agents"
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        return root


if __name__ == "__main__":
    unittest.main()

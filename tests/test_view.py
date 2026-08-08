from pathlib import Path
import os
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.memory import archive_memory, write_memory_structured
from at_runtime.view import render_memory_tree
from at_runtime.workspace import initialize_workspace


class ViewTests(unittest.TestCase):
    def test_tree_shows_tiers_and_medium_detail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://session/A/short", conclusion="draft note")
            write_memory_structured(
                root,
                "memory://task/T17/medium",
                conclusion="root cause",
                constraints=["keep schema"],
            )
            tree = render_memory_tree(root)
            self.assertIn("memory", tree)
            self.assertIn("short", tree)
            self.assertIn("medium", tree)
            self.assertIn("long", tree)
            self.assertIn("root cause", tree)
            self.assertIn("task-T17", tree)

    def test_short_collapsed_by_default_and_expanded_with_all(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://session/A/short", conclusion="draft note")
            self.assertNotIn("draft note", render_memory_tree(root))
            self.assertIn("draft note", render_memory_tree(root, include_all=True))

    def test_tree_hides_inactive_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(
                root, "memory://task/T17/medium", conclusion="hidden", source={"project": "P"}
            )
            archive_memory(root, "memory://task/T17/medium")
            self.assertNotIn("hidden", render_memory_tree(root))
            self.assertIn("hidden", render_memory_tree(root, include_all=True))


class CliMemoryTests(unittest.TestCase):
    def test_cli_promote_accepts_uri_and_to(self):
        from at_runtime.cli import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(
                root, "memory://session/A/short", conclusion="note", source={"task": "T17"}
            )
            old = os.getcwd()
            os.chdir(root)
            try:
                code = main(["memory", "promote", "memory://session/A/short", "--to", "medium"])
            finally:
                os.chdir(old)
            self.assertEqual(code, 0)
            self.assertTrue((root / ".agent/memory/medium/task-T17.md").exists())


if __name__ == "__main__":
    unittest.main()

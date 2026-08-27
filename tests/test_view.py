from pathlib import Path
import os
import json
import contextlib
import io
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot_memory.memory import archive_memory, write_memory_structured
from xiaot_memory.view import render_memory_export, render_memory_stats, render_memory_tree
from xiaot_memory.workspace import initialize_workspace


class ViewTests(unittest.TestCase):
    def test_tree_shows_tiers_and_medium_detail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://session/A/short", conclusion="draft note", source={"task": "T17"})
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
            write_memory_structured(root, "memory://session/A/short", conclusion="draft note", source={"task": "T17"})
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
        from xiaot_memory.cli import main

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

    def test_cli_rollback_unknown_clean_error(self):
        from xiaot_memory.cli import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            old = os.getcwd()
            os.chdir(root)
            try:
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    code = main(["memory", "rollback", "nonexistent-id"])
            finally:
                os.chdir(old)
            self.assertEqual(code, 1)
            self.assertIn("error:", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())


class ExportTests(unittest.TestCase):
    def test_export_contains_tiers_and_entry_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(
                root,
                "memory://task/T17/medium",
                conclusion="root cause",
                constraints=["keep schema"],
                unresolved=["threshold?"],
                source={"project": "P"},
            )
            report = render_memory_export(root)
            self.assertIn("# AT Memory Export", report)
            self.assertIn("## short", report)
            self.assertIn("## medium", report)
            self.assertIn("## long", report)
            self.assertIn("root cause", report)
            self.assertIn("keep schema", report)
            self.assertIn("threshold?", report)
            self.assertIn("task-T17", report)

    def test_export_hides_inactive_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://session/A/short", conclusion="hidden", source={"task": "T17"})
            archive_memory(root, "memory://session/A/short")
            self.assertNotIn("hidden", render_memory_export(root))
            self.assertIn("hidden", render_memory_export(root, include_all=True))


class CliExportTests(unittest.TestCase):
    def test_cli_export_writes_file(self):
        from xiaot_memory.cli import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://task/T17/medium", conclusion="root cause")
            old = os.getcwd()
            os.chdir(root)
            try:
                code = main(["memory", "export"])
            finally:
                os.chdir(old)
            self.assertEqual(code, 0)
            exports = list((root / ".agent/export").glob("memory-*.md"))
            self.assertEqual(len(exports), 1)
            self.assertIn("root cause", exports[0].read_text(encoding="utf-8"))


class StatsTests(unittest.TestCase):
    def test_stats_empty_workspace_zeros(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            stats = render_memory_stats(root)
            self.assertEqual(stats["total"], 0)
            self.assertEqual(stats["checkpoints"], 0)
            for tier in ("short", "medium", "long"):
                self.assertEqual(stats["tiers"][tier]["total"], 0)

    def test_stats_counts_entries_and_hides_inactive_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://session/A/short", conclusion="draft", source={"task": "T17"})
            write_memory_structured(
                root, "memory://task/T17/medium", conclusion="root cause", source={"project": "P"}
            )
            write_memory_structured(
                root, "memory://task/T18/medium", conclusion="hidden", source={"project": "P"}
            )
            archive_memory(root, "memory://task/T18/medium")
            stats = render_memory_stats(root)
            self.assertEqual(stats["tiers"]["short"]["total"], 1)
            self.assertEqual(stats["tiers"]["medium"]["total"], 1)
            self.assertEqual(stats["tiers"]["medium"]["archived"], 0)
            stats_all = render_memory_stats(root, include_all=True)
            self.assertEqual(stats_all["tiers"]["medium"]["total"], 2)
            self.assertEqual(stats_all["tiers"]["medium"]["archived"], 1)

    def test_stats_counts_checkpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            from xiaot_memory.timeline import create_checkpoint
            create_checkpoint(root, "c1")
            self.assertEqual(render_memory_stats(root)["checkpoints"], 1)


class CliStatsTests(unittest.TestCase):
    def test_cli_stats_prints_json(self):
        from xiaot_memory.cli import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://task/T17/medium", conclusion="root cause")
            old = os.getcwd()
            os.chdir(root)
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = main(["memory", "stats"])
            finally:
                os.chdir(old)
            self.assertEqual(code, 0)
            data = json.loads(buf.getvalue())
            self.assertEqual(data["tiers"]["medium"]["total"], 1)


if __name__ == "__main__":
    unittest.main()

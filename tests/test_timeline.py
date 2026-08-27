from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot_memory.memory import read_memory, write_memory_structured
from xiaot_memory.timeline import create_checkpoint, list_checkpoints, rollback_memory
from xiaot_memory.view import render_memory_stats
from xiaot_memory.workspace import initialize_workspace


def _note(root, uri, text):
    write_memory_structured(root, uri, conclusion=text, source={"task": "T17"})


class TimelineTests(unittest.TestCase):
    def test_checkpoint_and_list(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            _note(root, "memory://session/A/short", "note")
            node = create_checkpoint(root, "fix beam stability")
            self.assertTrue(node["id"].endswith("fix-beam-stability"))
            checkpoints = list_checkpoints(root)
            self.assertEqual(len(checkpoints), 1)
            self.assertEqual(checkpoints[0]["label"], "fix beam stability")

    def test_rollback_restores_memory_and_creates_recovery_point(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            _note(root, "memory://session/A/short", "original")
            node = create_checkpoint(root, "before-change")
            _note(root, "memory://session/A/short", "changed")
            rollback_memory(root, node["id"])
            entries = read_memory(root, "memory://session/A/short")
            self.assertEqual(entries[-1]["content"], "original")
            checkpoints = list_checkpoints(root)
            self.assertEqual(len(checkpoints), 2)  # 原节点 + 自动恢复点
            self.assertTrue(checkpoints[0]["label"].startswith("pre-rollback"))

    def test_checkpoint_counts_entries_not_files(self):
        # issue-3：一个 .md 文件含多条 entry 时，checkpoint 与 stats 总数必须一致
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            for i in range(3):
                _note(root, "memory://session/A/short", f"entry-{i}")
            node = create_checkpoint(root, "multi-entry")
            stats = render_memory_stats(root)
            self.assertEqual(node["tiers"]["short"], stats["tiers"]["short"]["total"])
            self.assertEqual(node["tiers"]["short"], 3)


if __name__ == "__main__":
    unittest.main()

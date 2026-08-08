from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.memory import read_memory, write_memory_structured
from at_runtime.timeline import create_checkpoint, list_checkpoints, rollback_memory
from at_runtime.workspace import initialize_workspace


class TimelineTests(unittest.TestCase):
    def test_checkpoint_and_list(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://session/A/short", conclusion="note")
            node = create_checkpoint(root, "fix beam stability")
            self.assertTrue(node["id"].endswith("fix-beam-stability"))
            checkpoints = list_checkpoints(root)
            self.assertEqual(len(checkpoints), 1)
            self.assertEqual(checkpoints[0]["label"], "fix beam stability")

    def test_rollback_restores_memory_and_creates_recovery_point(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://session/A/short", conclusion="original")
            node = create_checkpoint(root, "before-change")
            write_memory_structured(root, "memory://session/A/short", conclusion="changed")
            rollback_memory(root, node["id"])
            entries = read_memory(root, "memory://session/A/short")
            self.assertEqual(entries[-1]["content"], "original")
            checkpoints = list_checkpoints(root)
            self.assertEqual(len(checkpoints), 2)  # 原节点 + 自动恢复点
            self.assertTrue(checkpoints[0]["label"].startswith("pre-rollback"))


if __name__ == "__main__":
    unittest.main()

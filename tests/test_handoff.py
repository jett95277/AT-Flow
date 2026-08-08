from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.handoff import create_handoff, get_handoff
from at_runtime.workspace import initialize_workspace


class HandoffTests(unittest.TestCase):
    def test_handoff_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            handoff = create_handoff(
                root,
                "H-T17-A-C",
                "analysis",
                "code",
                "T17",
                {
                    "conclusion": {"root_cause": "beam < 2"},
                    "constraints": ["keep skipped"],
                },
            )
            loaded = get_handoff(root, "H-T17-A-C")
            self.assertEqual(loaded["conclusion"]["root_cause"], "beam < 2")
            self.assertEqual(loaded["to"], "code")


if __name__ == "__main__":
    unittest.main()

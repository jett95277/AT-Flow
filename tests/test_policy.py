from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.policy import can_read, can_write
from at_runtime.workspace import initialize_workspace, load_policies


class PolicyTests(unittest.TestCase):
    def test_code_can_read_analysis_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            policies = load_policies(root)
            self.assertTrue(can_read(policies, "code", "handoff:analysis_to_code"))
            self.assertFalse(can_read(policies, "code", "handoff:test_to_code"))

    def test_analysis_cannot_write_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            policies = load_policies(root)
            self.assertFalse(can_write(policies, "analysis", "source"))
            self.assertTrue(can_write(policies, "code", "source"))


if __name__ == "__main__":
    unittest.main()

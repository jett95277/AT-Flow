from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.eval import run_minimal_eval
from at_runtime.workspace import initialize_workspace


class EvalTests(unittest.TestCase):
    def test_eval_reports_both_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            result = run_minimal_eval(root, "fix beam stability", provider="mock")
            self.assertIn("baseline", result)
            self.assertIn("at_flow", result)
            self.assertIn("task_success", result["baseline"])
            self.assertIn("estimated_tokens", result["at_flow"])

    def test_eval_tokens_come_from_injected_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            result = run_minimal_eval(root, "fix beam stability", provider="mock")
            self.assertTrue(result["baseline"]["task_success"])
            self.assertGreater(result["at_flow"]["estimated_tokens"], 0)
            self.assertEqual(result["at_flow"]["sessions"], 3)


if __name__ == "__main__":
    unittest.main()

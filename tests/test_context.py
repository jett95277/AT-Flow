from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.context import build_context, estimate_tokens
from at_runtime.registry import create_session, create_task
from at_runtime.workspace import initialize_workspace


class ContextTests(unittest.TestCase):
    def test_bundle_contains_task_handoff_and_constraints(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            create_task(root, "T17", "fix beam stability", {"project": "ASR-Agent"})
            create_session(root, "code-T17-01", "T17", "code", "codex")
            bundle = build_context(
                root,
                "code-T17-01",
                explicit_refs={
                    "handoff": {
                        "from": "analysis",
                        "to": "code",
                        "summary": "beam < 2 means stability skipped",
                    },
                    "constraints": ["preserve API schema"],
                    "source": ["src/scoring.py:120-160"],
                    "memory": ["memory://project/ASR-Agent/long"],
                },
            )
            self.assertEqual(bundle["task"]["id"], "T17")
            self.assertEqual(bundle["role"]["type"], "code")
            self.assertIn("preserve API schema", bundle["constraints"])
            self.assertEqual(
                bundle["handoff"]["summary"], "beam < 2 means stability skipped"
            )
            self.assertGreater(bundle["token_budget"]["max_context"], 0)

    def test_policy_filters_unreadable_refs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            create_task(root, "T18", "goal", {"project": "P"})
            create_session(root, "code-T18-01", "T18", "code", "codex")
            bundle = build_context(
                root,
                "code-T18-01",
                explicit_refs={
                    "handoff": {"from": "test", "to": "code", "summary": "denied"},
                    "constraints": ["keep"],
                    "source": ["src/a.py"],
                    "memory": [
                        "memory://project/P/long",
                        "memory://analysis/A/medium",
                    ],
                    "wiki": ["wiki://known"],
                },
            )
            self.assertEqual(bundle["handoff"]["summary"], "")
            self.assertEqual(
                bundle["relevant_memory"], ["memory://project/P/long"]
            )
            self.assertEqual(bundle["evidence"], [{"file": "src/a.py"}])
            self.assertEqual(bundle["knowledge"], ["wiki://known"])
            self.assertIn("handoff:test_to_code", bundle["policy"]["filtered"])
            self.assertIn("memory://analysis/A/medium", bundle["policy"]["filtered"])

    def test_estimate_tokens(self):
        self.assertGreater(estimate_tokens("hello world" * 100), 10)


if __name__ == "__main__":
    unittest.main()

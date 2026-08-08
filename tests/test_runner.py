from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.observer import list_events
from at_runtime.registry import get_session
from at_runtime.runner import run_doctor, run_task_flow
from at_runtime.workspace import initialize_workspace


class RunnerTests(unittest.TestCase):
    def test_three_session_flow_completes_with_mock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            steps = run_task_flow(
                root,
                "T17",
                "fix beam stability",
                {
                    "constraints": ["preserve API schema"],
                    "source": ["src/scoring.py"],
                },
                provider="mock",
            )
            self.assertEqual(
                [step["role"] for step in steps], ["analysis", "code", "test"]
            )
            self.assertTrue(all(step["status"] == "done" for step in steps))
            self.assertTrue((root / ".agent/handoffs" / "H-T17-A-C.yaml").exists())
            self.assertTrue((root / ".agent/handoffs" / "H-T17-C-T.yaml").exists())

    def test_doctor_reports_corrupt_session_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            (root / ".agent/runtime/sessions/bad.yaml").write_text(
                "{{{ not yaml", encoding="utf-8"
            )
            report = run_doctor(root)
            self.assertFalse(report["ok"])

    def test_flow_marks_failed_session_on_spawn_error(self):
        import at_runtime.runner as runner_module

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            original = runner_module.LocalAdapter

            class _Boom(original):
                def spawn(self, *args, **kwargs):
                    raise RuntimeError("boom")

            runner_module.LocalAdapter = _Boom
            try:
                with self.assertRaises(RuntimeError):
                    run_task_flow(root, "T18", "goal", {}, provider="codex")
            finally:
                runner_module.LocalAdapter = original
            session = get_session(root, "analysis-T18-01")
            self.assertEqual(session["status"], "failed")
            events = list_events(root)
            self.assertTrue(any(e["event"] == "session.failed" for e in events))


if __name__ == "__main__":
    unittest.main()

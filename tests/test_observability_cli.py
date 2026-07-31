from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.cli import main
from at_flow.engine import Runner
from at_flow.models import SessionState
from at_flow.workspace import ATWorkspace


class ObservabilityCliTests(unittest.TestCase):
    def test_trace_audit_artifact_and_doctor_commands_show_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = ATWorkspace.init(root)
            session = SessionState.new(
                task="observable session",
                project_path=workspace.projects_root / "demo",
                provider="mock",
                pipeline=["main"],
            )
            workspace.create_session(session)
            result = Runner(workspace).run(session.id)
            self.assertTrue(result.is_complete())

            trace_output = _run_cli("--root", str(root), "trace", session.id)
            self.assertIn("prepare_agent", trace_output)
            self.assertIn("build_context", trace_output)
            self.assertIn("collect_output", trace_output)

            audit_output = _run_cli("--root", str(root), "audit", session.id)
            self.assertIn("00-main.json", audit_output)
            self.assertIn("violations: 0", audit_output)

            artifact_output = _run_cli("--root", str(root), "artifact", session.id, "main")
            self.assertIn("## Task Summary", artifact_output)

            doctor_output = _run_cli("--root", str(root), "doctor")
            self.assertIn("config: OK", doctor_output)
            self.assertIn("agent:main: OK", doctor_output)
            self.assertIn("sessions_running: OK", doctor_output)


def _run_cli(*args: str) -> str:
    output = StringIO()
    with redirect_stdout(output):
        exit_code = main(list(args))
    if exit_code != 0:
        raise AssertionError(f"CLI exited with {exit_code}: {' '.join(args)}\n{output.getvalue()}")
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()

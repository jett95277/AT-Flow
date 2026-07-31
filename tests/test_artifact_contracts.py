from pathlib import Path
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.artifacts import validate_artifact_contract
from at_flow.engine import Runner
from at_flow.models import SessionState
from at_flow.trace import read_trace_events
from at_flow.workspace import ATWorkspace


class ArtifactContractTests(unittest.TestCase):
    def test_validate_artifact_contract_reports_missing_sections(self) -> None:
        output_contract = """# code output contract

Write `outbox/artifact.md` with these sections:

- Changed Files
- Behavioral Changes
- Verification Suggestions
"""
        artifact = """# code artifact

## Changed Files

- src/app.py
"""

        missing = validate_artifact_contract("code", output_contract, artifact)

        self.assertEqual(missing, ["Behavioral Changes", "Verification Suggestions"])

    def test_runner_fails_step_when_artifact_contract_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            script = _write_provider(
                Path(directory),
                "incomplete_artifact.py",
                """
                print("# main artifact")
                print()
                print("## Task Summary")
                print()
                print("Only one required section.")
                """,
            )
            workspace.config["providers"]["incomplete-artifact"] = _provider(script)
            session = SessionState.new(
                task="invalid artifact",
                project_path=workspace.projects_root / "demo",
                provider="incomplete-artifact",
                pipeline=["main"],
            )
            workspace.create_session(session)

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.has_failed())
            self.assertIn("Artifact contract failed", result.steps[0].error or "")
            self.assertTrue(result.steps[0].retryable)
            events = read_trace_events(workspace.session_dir(session.id) / "trace.jsonl")
            self.assertIn("artifact_contract_failed", [event["event"] for event in events])


def _provider(script: Path) -> dict[str, object]:
    return {
        "type": "process",
        "command": [sys.executable, str(script)],
        "prompt_mode": "stdin",
        "cwd": "workspace",
        "env_policy": "minimal",
        "timeout_seconds": 30,
    }


def _write_provider(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.artifacts import validate_artifact_contract, validate_runtime_artifact_language
from at_flow.engine import Runner
from at_flow.models import SessionState
from at_flow.trace import read_trace_events
from at_flow.workspace import ATWorkspace


class ArtifactContractTests(unittest.TestCase):
    def test_runtime_language_validator_ignores_cjk_inside_fenced_code(self) -> None:
        artifact = """# code artifact

## Changed Files

Updated the greeting.

```python
print("你好")
```
"""

        violations = validate_runtime_artifact_language(artifact, "en")

        self.assertEqual(violations, [])

    def test_runtime_language_validator_reports_cjk_narrative_for_english_runtime(self) -> None:
        artifact = """# code artifact

## Changed Files

修改了登录模块。
"""

        violations = validate_runtime_artifact_language(artifact, "en")

        self.assertEqual(violations, ["line 5 contains CJK narrative"])

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

    def test_runner_fails_english_runtime_artifact_with_cjk_narrative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            workspace.config["language"] = {
                "enabled": True,
                "source": "auto",
                "runtime": "en",
                "display": "zh",
                "translation_provider": "",
                "required": True,
                "translate_artifacts": False,
            }
            script = _write_provider(
                Path(directory),
                "chinese_artifact.py",
                """
                import sys

                sys.stdout.reconfigure(encoding="utf-8")
                print("# main artifact")
                print()
                for heading in (
                    "Task Summary", "Goal", "Non-Goals", "Constraints",
                    "Acceptance Criteria", "Risks And Questions", "Handoff To Analysis"
                ):
                    print(f"## {heading}")
                    print()
                    print("这里是中文说明。")
                    print()
                """,
            )
            workspace.config["providers"]["chinese-artifact"] = _provider(script)
            session = SessionState.new(
                task="Implement login",
                project_path=workspace.projects_root / "demo",
                provider="chinese-artifact",
                pipeline=["main"],
            )
            workspace.create_session(session)

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.has_failed())
            self.assertIn("Artifact language contract failed", result.steps[0].error or "")
            events = read_trace_events(workspace.session_dir(session.id) / "trace.jsonl")
            self.assertIn("artifact_language_failed", [event["event"] for event in events])


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

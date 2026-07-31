from pathlib import Path
import json
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.engine import Runner
from at_flow.models import SessionState
from at_flow.schema import validate_session_state
from at_flow.trace import read_trace_events
from at_flow.transitions import (
    TransitionError,
    recover_interrupted_step,
    retry_failed_step,
    transition_step,
)
from at_flow.workspace import ATWorkspace


class RuntimeContractsTests(unittest.TestCase):
    def test_session_schema_exposes_status_current_stage_and_retry_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = SessionState.new(
                task="schema task",
                project_path=Path(directory) / "project",
                provider="mock",
            )

            data = session.to_dict()

            self.assertEqual(data["schema_version"], 1)
            self.assertEqual(data["status"], "queued")
            self.assertEqual(data["current_stage"], "main")
            self.assertIsNone(data["failure_reason"])
            self.assertEqual(data["steps"][0]["retry_count"], 0)
            self.assertEqual(data["steps"][0]["max_retries"], 1)
            self.assertTrue(data["steps"][0]["retryable"])
            validate_session_state(data)

    def test_stage_transition_rules_reject_invalid_jumps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = SessionState.new(
                task="transition task",
                project_path=Path(directory) / "project",
                provider="mock",
                pipeline=["main"],
            )

            with self.assertRaises(TransitionError):
                transition_step(session, 0, "done")

            transition_step(session, 0, "running")
            transition_step(session, 0, "failed", error="provider failed", retryable=True)
            retry_failed_step(session, 0)
            self.assertEqual(session.steps[0].status, "retrying")
            self.assertEqual(session.steps[0].retry_count, 1)
            transition_step(session, 0, "running")
            transition_step(session, 0, "done", artifact_path="artifact.md")

            self.assertTrue(session.is_complete())
            self.assertEqual(session.status, "done")

    def test_running_step_can_be_marked_failed_during_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = SessionState.new(
                task="interrupted task",
                project_path=Path(directory) / "project",
                provider="mock",
                pipeline=["main"],
            )
            transition_step(session, 0, "running")

            self.assertEqual(session.interrupted_steps(), [0])

            recover_interrupted_step(session, 0, "runner restarted")

            self.assertTrue(session.has_failed())
            self.assertEqual(session.status, "failed")
            self.assertEqual(session.current_stage, "main")
            self.assertTrue(session.steps[0].retryable)
            self.assertIn("runner restarted", session.steps[0].failure_reason or "")

    def test_runner_writes_trace_events_and_structured_error_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            script = _write_provider(
                Path(directory),
                "fail_provider.py",
                """
                import sys
                print("structured boom", file=sys.stderr)
                raise SystemExit(7)
                """,
            )
            workspace.config["providers"]["fail-provider"] = _provider(script)
            session = SessionState.new(
                task="trace failure",
                project_path=workspace.projects_root / "demo",
                provider="fail-provider",
                pipeline=["main"],
            )
            workspace.create_session(session)

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.has_failed())
            self.assertEqual(result.status, "failed")
            self.assertIn("Provider fail-provider failed", result.failure_reason or "")
            failure_path = Path(result.steps[0].artifact_path)
            failure = json.loads(failure_path.read_text(encoding="utf-8"))
            self.assertEqual(failure["agent"], "main")
            self.assertEqual(failure["status"], "failed")
            self.assertIn("Provider fail-provider failed", failure["error"])

            events = read_trace_events(workspace.session_dir(session.id) / "trace.jsonl")
            names = [event["event"] for event in events]
            self.assertIn("prepare_agent", names)
            self.assertIn("route_prior_handoff", names)
            self.assertIn("run_agent_start", names)
            self.assertIn("run_agent_failed", names)
            self.assertIn("collect_output", names)
            self.assertIn("audit_permissions", names)
            self.assertIn("transition_state", names)

    def test_failed_session_can_retry_same_stage_and_then_continue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            flag = Path(directory) / "attempt.flag"
            script = _write_provider(
                Path(directory),
                "flaky_provider.py",
                f"""
                from pathlib import Path
                import os
                import sys

                flag = Path({str(flag)!r})
                if not flag.exists():
                    flag.write_text("failed once", encoding="utf-8")
                    print("first attempt failed", file=sys.stderr)
                    raise SystemExit(3)

                Path(os.environ["AT_OUTBOX"], "artifact.md").write_text(
                    "# main artifact\\n\\n"
                    "## Task Summary\\n\\nRetry passed.\\n\\n"
                    "## Goal\\n\\nComplete retry.\\n\\n"
                    "## Non-Goals\\n\\nNo extra work.\\n\\n"
                    "## Constraints\\n\\nStay in retry step.\\n\\n"
                    "## Acceptance Criteria\\n\\nArtifact is fresh.\\n\\n"
                    "## Risks And Questions\\n\\nNone.\\n\\n"
                    "## Handoff To Analysis\\n\\nRetry passed.\\n",
                    encoding="utf-8"
                )
                """,
            )
            workspace.config["providers"]["flaky"] = _provider(script)
            session = SessionState.new(
                task="retry task",
                project_path=workspace.projects_root / "demo",
                provider="flaky",
                pipeline=["main"],
            )
            workspace.create_session(session)

            failed = Runner(workspace).run(session.id)
            self.assertTrue(failed.has_failed())

            retried = Runner(workspace).retry(session.id)

            self.assertTrue(retried.is_complete())
            self.assertEqual(retried.steps[0].retry_count, 1)
            self.assertIn("## Task Summary", Path(retried.steps[0].artifact_path).read_text(encoding="utf-8"))

    def test_retry_clears_stale_outbox_artifacts_before_provider_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            flag = Path(directory) / "attempt.flag"
            script = _write_provider(
                Path(directory),
                "stale_artifact_provider.py",
                f"""
                from pathlib import Path
                import os
                import sys

                flag = Path({str(flag)!r})
                artifact = Path(os.environ["AT_OUTBOX"], "artifact.md")
                if not flag.exists():
                    flag.write_text("failed once", encoding="utf-8")
                    artifact.write_text("stale artifact", encoding="utf-8")
                    print("failed after stale artifact", file=sys.stderr)
                    raise SystemExit(4)

                print("# main artifact")
                print()
                print("## Task Summary")
                print()
                print("fresh retry artifact")
                print()
                print("## Goal")
                print()
                print("Complete retry.")
                print()
                print("## Non-Goals")
                print()
                print("No extra work.")
                print()
                print("## Constraints")
                print()
                print("Use fresh output.")
                print()
                print("## Acceptance Criteria")
                print()
                print("No stale artifact reused.")
                print()
                print("## Risks And Questions")
                print()
                print("None.")
                print()
                print("## Handoff To Analysis")
                print()
                print("Retry produced a fresh artifact.")
                """,
            )
            workspace.config["providers"]["stale-artifact"] = _provider(script)
            session = SessionState.new(
                task="retry stale artifact",
                project_path=workspace.projects_root / "demo",
                provider="stale-artifact",
                pipeline=["main"],
            )
            workspace.create_session(session)

            failed = Runner(workspace).run(session.id)
            self.assertTrue(failed.has_failed())
            stale_path = workspace.session_agent_outbox_dir(session.id, "main") / "artifact.md"
            self.assertEqual(stale_path.read_text(encoding="utf-8"), "stale artifact")

            retried = Runner(workspace).retry(session.id)

            self.assertTrue(retried.is_complete())
            self.assertIn("fresh retry artifact", Path(retried.steps[0].artifact_path).read_text(encoding="utf-8"))
            self.assertFalse((workspace.session_agent_outbox_dir(session.id, "main") / "failure.json").exists())

    def test_runner_recovers_running_step_before_continuing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="recover interrupted runner",
                project_path=workspace.projects_root / "demo",
                provider="mock",
                pipeline=["main", "analysis"],
            )
            workspace.create_session(session)
            transition_step(session, 0, "running")
            workspace.save_session(session)

            recovered = Runner(workspace).run(session.id)

            self.assertTrue(recovered.has_failed())
            self.assertEqual(recovered.current_stage, "main")
            self.assertEqual(recovered.steps[0].status, "failed")
            self.assertEqual(recovered.steps[1].status, "queued")
            self.assertTrue(recovered.steps[0].retryable)

            events = read_trace_events(workspace.session_dir(session.id) / "trace.jsonl")
            self.assertIn("recover_interrupted_step", [event["event"] for event in events])


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

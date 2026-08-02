from pathlib import Path
import json
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.engine import Runner
from at_flow.models import SessionState
from at_flow.web.errors import ApiError
from at_flow.web.runtime_service import RuntimeService
from at_flow.workspace import ATWorkspace


class RuntimeServiceTests(unittest.TestCase):
    def test_list_sessions_returns_empty_list_for_initialized_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            self.assertEqual(RuntimeService(workspace).list_sessions(), [])

    def test_get_state_returns_session_dict(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main", "analysis", "code", "test"],
                session_id="demo-session",
            )
            workspace.create_session(session)

            state = RuntimeService(workspace).get_state("demo-session")

            self.assertEqual(state["id"], "demo-session")
            self.assertEqual(
                [step["agent"] for step in state["steps"]],
                ["main", "analysis", "code", "test"],
            )

    def test_get_state_maps_unknown_session_to_api_error(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            with self.assertRaises(ApiError) as raised:
                RuntimeService(workspace).get_state("missing")

            self.assertEqual(raised.exception.code, "session_not_found")
            self.assertFalse(raised.exception.retryable)

    def test_get_trace_returns_trace_events(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="trace-session",
            )
            workspace.create_session(session)
            Runner(workspace).run(session.id)

            events = RuntimeService(workspace).get_trace("trace-session")

            self.assertTrue(events)
            self.assertTrue(any(event["event"] == "collect_output" for event in events))

    def test_get_audit_returns_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="audit-session",
            )
            workspace.create_session(session)
            Runner(workspace).run(session.id)

            reports = RuntimeService(workspace).get_audit("audit-session")

            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0]["agent"], "main")

    def test_get_artifact_returns_structured_source_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="artifact-session",
            )
            workspace.create_session(session)
            Runner(workspace).run(session.id)

            artifact = RuntimeService(workspace).get_artifact("artifact-session", "main")

            self.assertIn("## Task Summary", artifact["source"])
            self.assertIsNone(artifact["display"])
            self.assertEqual(artifact["source_language"], "en")
            self.assertEqual(artifact["display_status"], "disabled")

    def test_agent_display_artifact_remains_completed_after_later_translation_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="completed-display-session",
            )
            workspace.create_session(session)
            Runner(workspace).run(session.id)
            outbox = workspace.session_agent_outbox_dir(session.id, "main")
            (outbox / "artifact.zh.md").write_text("# 中文产物\n", encoding="utf-8")
            language_path = workspace.session_dir(session.id) / "language.json"
            language = json.loads(language_path.read_text(encoding="utf-8"))
            language["display_translation"] = {
                "status": "failed",
                "provider": "codex",
                "error": "later Agent translation failed",
                "updated_at": "2026-08-02T00:00:00+00:00",
            }
            language_path.write_text(
                json.dumps(language, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            artifact = RuntimeService(workspace).get_artifact(session.id, "main")

            self.assertEqual(artifact["display"], "# 中文产物\n")
            self.assertEqual(artifact["display_status"], "completed")
            self.assertIsNone(artifact["display_error"])

    def test_get_artifact_returns_empty_text_when_agent_has_no_artifact_yet(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="pending-artifact-session",
            )
            workspace.create_session(session)

            artifact = RuntimeService(workspace).get_artifact("pending-artifact-session", "main")

            self.assertEqual(artifact["source"], "")
            self.assertIsNone(artifact["display"])

    def test_get_language_returns_profile_before_session_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="任务",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="language-view-session",
            )
            workspace.create_session(session)

            language = RuntimeService(workspace).get_language(session.id)

            self.assertEqual(language["schema_version"], 2)
            self.assertEqual(language["task_original"], "任务")
            self.assertEqual(language["input_translation"]["status"], "disabled")


if __name__ == "__main__":
    unittest.main()

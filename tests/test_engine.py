from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.engine import Runner
from at_flow.models import SessionState
from at_flow.workspace import ATWorkspace


class EngineTests(unittest.TestCase):
    def test_mock_pipeline_completes_all_agents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            self.assertTrue(workspace.agent_profile_path("main").exists())
            self.assertTrue(workspace.agent_permissions_path("main").exists())
            self.assertTrue(workspace.agent_output_path("main").exists())
            session = SessionState.new(
                task="demo task",
                project_path=workspace.projects_root / "demo",
                provider="mock",
            )
            workspace.create_session(session)
            session_profile = workspace.session_dir(session.id) / "agents" / "main" / "agent.md"
            self.assertTrue(session_profile.exists())
            for agent in ("main", "analysis", "code", "test"):
                agent_dir = workspace.session_agent_dir(session.id, agent)
                self.assertTrue((agent_dir / "permissions.json").exists())
                self.assertTrue((agent_dir / "output.md").exists())
                self.assertTrue((agent_dir / "inbox").exists())
                self.assertTrue((agent_dir / "outbox").exists())
                self.assertTrue((agent_dir / "workspace").exists())

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.is_complete())
            self.assertEqual([step.agent for step in result.steps], ["main", "analysis", "code", "test"])
            for step in result.steps:
                self.assertEqual(step.status, "done")
                self.assertIsNotNone(step.artifact_path)
                self.assertTrue(Path(step.artifact_path).exists())
                self.assertEqual(Path(step.artifact_path).parent.name, "outbox")
                prompt_path = workspace.session_dir(session.id) / "agents" / step.agent / "prompt.md"
                prompt = prompt_path.read_text(encoding="utf-8")
                self.assertIn("Agent Contract (`agent.md`):", prompt)
                self.assertIn("Agent Permissions (`permissions.json`):", prompt)
                self.assertIn("Output Contract (`output.md`):", prompt)
                audit_path = workspace.session_dir(session.id) / "audit" / f"{result.steps.index(step):02d}-{step.agent}.json"
                self.assertTrue(audit_path.exists())

            code_inbox = workspace.session_agent_inbox_dir(session.id, "code")
            self.assertTrue((code_inbox / "00-main-artifact.md").exists())
            self.assertTrue((code_inbox / "01-analysis-artifact.md").exists())

    def test_permission_audit_fails_non_code_project_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            bad_script = Path(directory) / "bad_provider.py"
            bad_script.write_text(
                "from pathlib import Path\n"
                "import os\n"
                f"project = Path({str(workspace.projects_root / 'demo')!r})\n"
                "(project / 'violation.txt').write_text('bad')\n"
                "print('wrote outside permission')\n",
                encoding="utf-8",
            )
            workspace.config["providers"]["bad"] = {
                "type": "process",
                "command": [sys.executable, str(bad_script)],
                "prompt_mode": "stdin",
                "cwd": "workspace",
                "timeout_seconds": 30,
            }
            session = SessionState.new(
                task="bad write",
                project_path=workspace.projects_root / "demo",
                provider="bad",
                pipeline=["main"],
            )
            workspace.create_session(session)

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.has_failed())
            self.assertIn("Permission audit failed", result.steps[0].error or "")
            audit_path = workspace.session_dir(session.id) / "audit" / "00-main.json"
            self.assertIn("project", audit_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

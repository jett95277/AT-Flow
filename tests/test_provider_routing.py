from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.providers import resolve_agent_provider
from at_flow.engine import Runner
from at_flow.models import SessionState
from at_flow.workspace import ATWorkspace


class ProviderRoutingTests(unittest.TestCase):
    def test_explicit_session_provider_overrides_agent_route(self):
        config = {"agent_providers": {"code": "codex"}}

        self.assertEqual(resolve_agent_provider(config, "mock", "code"), "mock")
        self.assertEqual(resolve_agent_provider(config, "opencode", "code"), "opencode")

    def test_auto_provider_uses_agent_route(self):
        config = {"agent_providers": {"code": "codex", "test": "codex"}}

        self.assertEqual(resolve_agent_provider(config, "auto", "code"), "codex")
        self.assertEqual(resolve_agent_provider(config, "auto", "test"), "codex")

    def test_auto_provider_falls_back_to_default_provider(self):
        config = {"agent_providers": {"code": "codex"}, "default_provider": "mock"}

        self.assertEqual(resolve_agent_provider(config, "auto", "main"), "mock")

    def test_session_provider_is_fallback_when_no_agent_route_exists(self):
        self.assertEqual(resolve_agent_provider({}, "mock", "main"), "mock")

    def test_default_codex_provider_is_process_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            codex = workspace.config["providers"]["codex"]

            self.assertEqual(codex["type"], "process")
            self.assertEqual(codex["command"][0], "codex")
            self.assertEqual(codex["cwd"], "workspace")
            self.assertEqual(codex["env_policy"], "minimal")

    def test_engine_uses_agent_provider_route_for_code_step(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            workspace.config["agent_providers"] = {"code": "mock"}
            session = SessionState.new(
                task="route code",
                project_path=workspace.projects_root / "default",
                provider="auto",
                pipeline=["code"],
                session_id="route-code-session",
            )
            workspace.create_session(session)

            result = Runner(workspace).run("route-code-session", one_step=True)

            self.assertEqual(result.steps[0].status, "done")

    def test_process_provider_stderr_never_contaminates_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            script = (
                "import sys; "
                "sys.stderr.write('PROVIDER_DIAGNOSTIC\\n'); "
                "print('## Task Summary\\ndemo\\n## Goal\\ng\\n## Non-Goals\\nn\\n## Constraints\\nc\\n## Acceptance Criteria\\na\\n## Risks And Questions\\nr\\n## Handoff To Analysis\\nh')"
            )
            workspace.config["providers"]["echo"] = {
                "type": "process",
                "command": [sys.executable, "-c", script],
                "prompt_mode": "stdin",
                "encoding": "utf-8",
                "cwd": "workspace",
                "env_policy": "minimal",
                "env_passthrough": ["PATH", "PATHEXT", "SystemRoot", "ComSpec", "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "LANG"],
                "timeout_seconds": 60,
            }
            workspace.config["agent_providers"] = {"main": "echo"}
            session = SessionState.new(
                task="stderr isolation",
                project_path=workspace.projects_root / "default",
                provider="auto",
                pipeline=["main"],
                session_id="stderr-isolation-session",
            )
            workspace.create_session(session)

            result = Runner(workspace).run("stderr-isolation-session", one_step=True)

            self.assertEqual(result.steps[0].status, "done")
            artifact_path = (
                workspace.session_agent_outbox_dir("stderr-isolation-session", "main")
                / "artifact.md"
            )
            artifact = artifact_path.read_text(encoding="utf-8")
            self.assertNotIn("PROVIDER_DIAGNOSTIC", artifact)
            stderr_log = (
                workspace.session_agent_dir("stderr-isolation-session", "main")
                / "provider.stderr.log"
            )
            self.assertTrue(stderr_log.is_file())
            self.assertIn("PROVIDER_DIAGNOSTIC", stderr_log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

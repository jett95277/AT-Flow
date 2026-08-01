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
    def test_agent_provider_route_overrides_session_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            workspace.config["agent_providers"] = {
                "main": "mock",
                "analysis": "mock",
                "code": "codex",
                "test": "codex",
            }

            self.assertEqual(resolve_agent_provider(workspace.config, "mock", "code"), "codex")
            self.assertEqual(resolve_agent_provider(workspace.config, "mock", "test"), "codex")

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
                provider="missing-provider",
                pipeline=["code"],
                session_id="route-code-session",
            )
            workspace.create_session(session)

            result = Runner(workspace).run("route-code-session", one_step=True)

            self.assertEqual(result.steps[0].status, "done")


if __name__ == "__main__":
    unittest.main()

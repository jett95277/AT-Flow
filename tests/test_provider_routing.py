from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.providers import resolve_agent_provider
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


if __name__ == "__main__":
    unittest.main()

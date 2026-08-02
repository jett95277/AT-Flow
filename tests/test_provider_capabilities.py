from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.config import default_config
from at_flow.providers import check_provider_capability, provider_capabilities


class ProviderCapabilityTests(unittest.TestCase):
    def test_mock_provider_is_available_without_external_command(self):
        result = check_provider_capability("mock", {"providers": {"mock": {"type": "mock"}}})

        self.assertEqual(result["name"], "mock")
        self.assertTrue(result["available"])
        self.assertEqual(result["provider_type"], "mock")

    def test_missing_process_provider_is_unavailable(self):
        result = check_provider_capability(
            "codex",
            {"providers": {"codex": {"type": "process", "command": ["definitely-missing-at-flow-command"]}}},
        )

        self.assertEqual(result["name"], "codex")
        self.assertFalse(result["available"])
        self.assertEqual(result["provider_type"], "process")
        self.assertIn("command not found", result["detail"])

    def test_unknown_provider_is_unavailable(self):
        result = check_provider_capability("missing", {"providers": {}})

        self.assertEqual(result["name"], "missing")
        self.assertFalse(result["available"])
        self.assertEqual(result["provider_type"], "unknown")

    def test_provider_capabilities_returns_all_configured_providers(self):
        result = provider_capabilities(default_config())

        names = [item["name"] for item in result]
        self.assertEqual(names, ["codex", "mock", "opencode"])
        self.assertTrue(all("available" in item for item in result))
        self.assertTrue(all("detail" in item for item in result))


if __name__ == "__main__":
    unittest.main()

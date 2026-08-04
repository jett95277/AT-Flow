from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.deploy_config import apply_sandbox, render_codex_config, write_opencode_config


class DeployConfigTests(unittest.TestCase):
    def test_render_codex_config_contains_deepseek_endpoint_and_key(self):
        text = render_codex_config("sk-test")
        self.assertIn("https://api.deepseek.com/", text)
        self.assertIn('experimental_bearer_token = "sk-test"', text)

    def test_apply_sandbox_changes_codex_sandbox_flag(self):
        config = {
            "providers": {
                "codex": {"command": ["codex", "exec", "--sandbox", "workspace-write", "-"]}
            }
        }
        updated, changed = apply_sandbox(config, "read-only")
        self.assertTrue(changed)
        cmd = updated["providers"]["codex"]["command"]
        self.assertEqual(cmd[cmd.index("--sandbox") + 1], "read-only")

    def test_apply_sandbox_noop_when_same(self):
        config = {
            "providers": {
                "codex": {"command": ["codex", "exec", "--sandbox", "read-only", "-"]}
            }
        }
        updated, changed = apply_sandbox(config, "read-only")
        self.assertFalse(changed)

    def test_apply_sandbox_handles_flag_at_end(self):
        config = {"providers": {"codex": {"command": ["codex", "exec", "--sandbox"]}}}
        updated, changed = apply_sandbox(config, "ignore")
        self.assertTrue(changed)
        self.assertEqual(updated["providers"]["codex"]["command"][-1], "ignore")

    def test_write_opencode_config_uses_container_root(self):
        result = write_opencode_config(Path("/opt/at-flow"))
        rules = result["permission"]["external_directory"]
        self.assertIn("/opt/at-flow/.at/shared/**", rules)
        self.assertIn("/opt/at-flow/.at/sessions/**", rules)


if __name__ == "__main__":
    unittest.main()

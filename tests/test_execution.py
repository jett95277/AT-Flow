from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.execution import build_prompt


class ExecutionTests(unittest.TestCase):
    def test_build_prompt_includes_bundle_parts(self):
        bundle = {
            "task": {"id": "T17", "goal": "fix beam stability"},
            "role": {"type": "code"},
            "constraints": ["preserve API schema"],
            "handoff": {"from": "analysis", "summary": "beam < 2"},
        }
        prompt = build_prompt(bundle, "code")
        self.assertIn("T17", prompt)
        self.assertIn("fix beam stability", prompt)
        self.assertIn("preserve API schema", prompt)
        self.assertIn("beam < 2", prompt)

    def test_local_adapter_command_uses_codex_exec(self):
        from at_runtime.execution import LocalAdapter

        adapter = LocalAdapter(command=["codex", "exec", "--ephemeral", "-"])
        command = adapter.spawn_command()
        self.assertEqual(command[0], "codex")
        self.assertIn("exec", command)


if __name__ == "__main__":
    unittest.main()

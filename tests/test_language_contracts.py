from pathlib import Path
import json
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.engine import Runner
from at_flow.models import SessionState
from at_flow.workspace import ATWorkspace


class LanguageContractTests(unittest.TestCase):
    def test_session_writes_language_contract_for_chinese_user_input(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            workspace.config["language"] = {
                "user": "zh",
                "runtime": "en",
                "display": "zh",
                "artifact_mode": "bilingual",
            }
            session = SessionState.new(
                task="帮我实现登录模块",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="language-session",
            )
            workspace.create_session(session)

            Runner(workspace).run("language-session", one_step=True)

            language_path = workspace.session_dir("language-session") / "language.json"
            context_path = workspace.session_dir("language-session") / "agents" / "main" / "context.json"
            language = json.loads(language_path.read_text(encoding="utf-8"))
            context = json.loads(context_path.read_text(encoding="utf-8"))

            self.assertEqual(language["task_original"], "帮我实现登录模块")
            self.assertEqual(language["runtime_language"], "en")
            self.assertEqual(language["display_language"], "zh")
            self.assertIn("task_runtime", language)
            self.assertEqual(context["language"]["runtime_language"], "en")

    def test_provider_prompt_uses_runtime_task_as_primary_task(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            workspace.config["language"] = {
                "user": "zh",
                "runtime": "en",
                "display": "zh",
                "artifact_mode": "bilingual",
            }
            session = SessionState.new(
                task="帮我实现登录模块",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="language-prompt-session",
            )
            workspace.create_session(session)

            Runner(workspace).run("language-prompt-session", one_step=True)

            prompt_path = workspace.session_agent_dir("language-prompt-session", "main") / "prompt.md"
            prompt = prompt_path.read_text(encoding="utf-8")

            task_section = prompt.split("Task:", 1)[1].split("Original User Task:", 1)[0]
            self.assertIn("Execute this user task in English runtime context.", task_section)
            self.assertIn("Original user task:", task_section)
            self.assertIn("帮我实现登录模块", task_section)
            self.assertIn("Original User Task:\n帮我实现登录模块", prompt)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.engine import Runner
from at_flow.language import LanguageService, TranslationError
from at_flow.models import SessionState
from at_flow.trace import read_trace_events
from at_flow.workspace import ATWorkspace


class FakeTranslator:
    name = "test-translator"

    def __init__(self, outputs: list[str] | None = None, failures: int = 0) -> None:
        self.outputs = list(outputs or ["Implement a login module for me", "# 中文展示\n\n任务已处理。"])
        self.failures = failures
        self.calls: list[tuple[str, str, str, str]] = []

    def translate(self, text: str, source_language: str, target_language: str, purpose: str) -> str:
        self.calls.append((text, source_language, target_language, purpose))
        if self.failures > 0:
            self.failures -= 1
            raise TranslationError("translation_process_failed", "translator offline", retryable=True)
        return self.outputs.pop(0)


class LanguageContractTests(unittest.TestCase):
    def test_chinese_user_input_is_translated_and_persisted_before_agent_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            self._enable_language(workspace)
            translator = FakeTranslator()
            session = self._session(workspace, "帮我实现登录模块", "language-session")

            result = Runner(workspace, language_service=LanguageService(workspace, translator=translator)).run(
                session.id,
                one_step=True,
            )

            language_path = workspace.session_dir(session.id) / "language.json"
            context_path = workspace.session_dir(session.id) / "agents" / "main" / "context.json"
            language = json.loads(language_path.read_text(encoding="utf-8"))
            context = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual(language["schema_version"], 2)
            self.assertEqual(language["task_original"], "帮我实现登录模块")
            self.assertEqual(language["task_runtime"], "Implement a login module for me")
            self.assertEqual(language["runtime_language"], "en")
            self.assertEqual(language["display_language"], "zh")
            self.assertEqual(language["input_translation"]["status"], "completed")
            self.assertEqual(language["input_translation"]["provider"], "test-translator")
            self.assertEqual(context["language"]["runtime_language"], "en")
            self.assertEqual(result.steps[0].status, "done")

    def test_english_input_does_not_call_translator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            self._enable_language(workspace)
            translator = FakeTranslator()
            session = self._session(workspace, "Implement a login module", "english-session")

            Runner(workspace, language_service=LanguageService(workspace, translator=translator)).run(
                session.id,
                one_step=True,
            )

            language = json.loads((workspace.session_dir(session.id) / "language.json").read_text(encoding="utf-8"))
            self.assertEqual(language["source_language"], "en")
            self.assertEqual(language["task_runtime"], "Implement a login module")
            self.assertEqual(language["input_translation"]["status"], "not_required")
            self.assertEqual([call[3] for call in translator.calls], ["artifact"])

    def test_disabled_language_conversion_does_not_claim_english_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            translator = FakeTranslator()
            session = self._session(workspace, "帮我实现登录模块", "disabled-session")

            Runner(workspace, language_service=LanguageService(workspace, translator=translator)).run(
                session.id,
                one_step=True,
            )

            language = json.loads((workspace.session_dir(session.id) / "language.json").read_text(encoding="utf-8"))
            self.assertEqual(language["runtime_language"], "zh")
            self.assertEqual(language["task_runtime"], "帮我实现登录模块")
            self.assertEqual(language["input_translation"]["status"], "disabled")
            self.assertEqual(translator.calls, [])

    def test_required_translation_failure_prevents_agent_provider_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = ATWorkspace.init(root)
            self._enable_language(workspace)
            marker = root / "provider-ran.txt"
            provider_script = root / "provider.py"
            provider_script.write_text(
                textwrap.dedent(
                    f"""
                    from pathlib import Path
                    Path({str(marker)!r}).write_text("ran", encoding="utf-8")
                    print("provider output")
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            workspace.config["providers"]["marker"] = {
                "type": "process",
                "command": [sys.executable, str(provider_script)],
                "prompt_mode": "stdin",
                "cwd": "workspace",
                "env_policy": "minimal",
            }
            translator = FakeTranslator(failures=1)
            session = self._session(workspace, "任务", "failure-session", provider="marker")

            result = Runner(workspace, language_service=LanguageService(workspace, translator=translator)).run(
                session.id,
                one_step=True,
            )

            self.assertEqual(result.steps[0].status, "failed")
            self.assertTrue(result.steps[0].retryable)
            self.assertIn("input_translation_failed", result.steps[0].error or "")
            self.assertFalse(marker.exists())
            language = json.loads((workspace.session_dir(session.id) / "language.json").read_text(encoding="utf-8"))
            self.assertEqual(language["input_translation"]["status"], "failed")
            events = read_trace_events(workspace.session_dir(session.id) / "trace.jsonl")
            self.assertIn("translation_failed", [event["event"] for event in events])

    def test_retry_restarts_failed_input_translation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            self._enable_language(workspace)
            translator = FakeTranslator(failures=1)
            session = self._session(workspace, "任务", "retry-translation-session")
            runner = Runner(workspace, language_service=LanguageService(workspace, translator=translator))

            first = runner.run(session.id, one_step=True)
            second = runner.retry(session.id, one_step=True)

            self.assertEqual(first.steps[0].status, "failed")
            self.assertEqual(second.steps[0].status, "done")
            self.assertEqual(len(translator.calls), 3)
            language = json.loads((workspace.session_dir(session.id) / "language.json").read_text(encoding="utf-8"))
            self.assertEqual(language["input_translation"]["status"], "completed")

    def test_completed_v2_profile_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            self._enable_language(workspace)
            translator = FakeTranslator()
            session = self._session(workspace, "任务", "reuse-language-session")
            language_path = workspace.session_dir(session.id) / "language.json"
            language_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "source_language": "zh",
                        "runtime_language": "en",
                        "display_language": "zh",
                        "artifact_mode": "bilingual",
                        "task_original": "任务",
                        "task_runtime": "Existing English task",
                        "input_translation": {
                            "status": "completed",
                            "provider": "prior-translator",
                            "error": None,
                            "updated_at": "2026-08-02T00:00:00Z",
                        },
                        "display_translation": {
                            "status": "pending",
                            "provider": "prior-translator",
                            "error": None,
                            "updated_at": "2026-08-02T00:00:00Z",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            Runner(workspace, language_service=LanguageService(workspace, translator=translator)).run(
                session.id,
                one_step=True,
            )

            self.assertEqual([call[3] for call in translator.calls], ["artifact"])
            language = json.loads(language_path.read_text(encoding="utf-8"))
            self.assertEqual(language["task_runtime"], "Existing English task")

    def test_legacy_wrapper_profile_is_retranslated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            self._enable_language(workspace)
            translator = FakeTranslator()
            session = self._session(workspace, "任务", "legacy-language-session")
            language_path = workspace.session_dir(session.id) / "language.json"
            language_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_language": "zh",
                        "runtime_language": "en",
                        "display_language": "zh",
                        "artifact_mode": "bilingual",
                        "task_original": "任务",
                        "task_runtime": "Execute in English. Original task: 任务",
                        "translation_status": "pending",
                        "translation_provider": "none",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            Runner(workspace, language_service=LanguageService(workspace, translator=translator)).run(
                session.id,
                one_step=True,
            )

            language = json.loads(language_path.read_text(encoding="utf-8"))
            self.assertEqual(language["schema_version"], 2)
            self.assertEqual(language["task_runtime"], "Implement a login module for me")
            self.assertEqual(len(translator.calls), 2)

    def test_provider_prompt_uses_translated_runtime_task_as_primary_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            self._enable_language(workspace)
            session = self._session(workspace, "帮我实现登录模块", "language-prompt-session")

            Runner(
                workspace,
                language_service=LanguageService(workspace, translator=FakeTranslator()),
            ).run(session.id, one_step=True)

            prompt = (workspace.session_agent_dir(session.id, "main") / "prompt.md").read_text(encoding="utf-8")
            task_section = prompt.split("Task:", 1)[1].split("Original User Task:", 1)[0]
            self.assertIn("Implement a login module for me", task_section)
            self.assertNotIn("帮我实现登录模块", prompt)
            self.assertNotIn('"task_original"', prompt)
            context = json.loads(
                (workspace.session_dir(session.id) / "context" / "main.json").read_text(encoding="utf-8")
            )
            self.assertEqual(context["task"], "Implement a login module for me")
            self.assertNotIn("task_original", context["language"])

    def test_successful_runtime_writes_chinese_display_artifact_and_keeps_english_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            self._enable_language(workspace)
            translator = FakeTranslator()
            session = self._session(workspace, "帮我实现登录模块", "display-artifact-session")

            result = Runner(
                workspace,
                language_service=LanguageService(workspace, translator=translator),
            ).run(session.id, one_step=True)

            outbox = workspace.session_agent_outbox_dir(session.id, "main")
            source = (outbox / "artifact.md").read_text(encoding="utf-8")
            display = (outbox / "artifact.zh.md").read_text(encoding="utf-8")
            handoff = (workspace.session_dir(session.id) / "handoff" / "00-main-artifact.md").read_text(encoding="utf-8")
            self.assertEqual(result.steps[0].status, "done")
            self.assertIn("Implement a login module for me", source)
            self.assertEqual(display, "# 中文展示\n\n任务已处理。\n")
            self.assertEqual(handoff, source)
            self.assertNotEqual(handoff, display)
            language = json.loads((workspace.session_dir(session.id) / "language.json").read_text(encoding="utf-8"))
            self.assertEqual(language["display_translation"]["status"], "completed")

    def test_display_translation_failure_keeps_valid_english_step_done(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            self._enable_language(workspace)
            translator = FakeTranslator(failures=1)
            session = self._session(workspace, "Implement a login module", "display-failure-session")

            result = Runner(
                workspace,
                language_service=LanguageService(workspace, translator=translator),
            ).run(session.id, one_step=True)

            outbox = workspace.session_agent_outbox_dir(session.id, "main")
            self.assertEqual(result.steps[0].status, "done")
            self.assertTrue((outbox / "artifact.md").exists())
            self.assertFalse((outbox / "artifact.zh.md").exists())
            language = json.loads((workspace.session_dir(session.id) / "language.json").read_text(encoding="utf-8"))
            self.assertEqual(language["display_translation"]["status"], "failed")
            self.assertIn("translator offline", language["display_translation"]["error"])
            events = read_trace_events(workspace.session_dir(session.id) / "trace.jsonl")
            failed = [event for event in events if event["event"] == "translation_failed"]
            self.assertTrue(any(event.get("data", {}).get("purpose") == "artifact" for event in failed))

    def _enable_language(self, workspace: ATWorkspace) -> None:
        workspace.config["language"] = {
            "enabled": True,
            "source": "auto",
            "runtime": "en",
            "display": "zh",
            "translation_provider": "test-translator",
            "required": True,
            "translate_artifacts": True,
        }

    def _session(
        self,
        workspace: ATWorkspace,
        task: str,
        session_id: str,
        *,
        provider: str = "mock",
    ) -> SessionState:
        session = SessionState.new(
            task=task,
            project_path=workspace.projects_root / "default",
            provider=provider,
            pipeline=["main"],
            session_id=session_id,
        )
        workspace.create_session(session)
        return session


if __name__ == "__main__":
    unittest.main()

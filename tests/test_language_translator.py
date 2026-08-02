from pathlib import Path
import os
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.language.translator import TranslationError, make_text_translator


class LanguageTranslatorTests(unittest.TestCase):
    def test_process_translator_returns_process_output_without_runtime_path_leaks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self._write_script(
                root,
                "translate.py",
                """
                import os
                import sys

                forbidden = [
                    "AT_PROJECT_PATH",
                    "AT_SHARED_MEMORY",
                    "AT_SHARED_SKILLS",
                    "AT_SHARED_INBOX",
                    "AT_AGENT_DIR",
                    "AT_SESSION_ID",
                ]
                leaked = [name for name in forbidden if name in os.environ]
                if leaked:
                    raise SystemExit("leaked: " + ",".join(leaked))
                if os.environ.get("AT_TRANSLATION_SOURCE") != "zh":
                    raise SystemExit("missing source language")
                if os.environ.get("AT_TRANSLATION_TARGET") != "en":
                    raise SystemExit("missing target language")
                if os.environ.get("AT_TRANSLATION_PURPOSE") != "task":
                    raise SystemExit("missing purpose")
                if "帮我实现登录模块" not in sys.stdin.buffer.read().decode("utf-8"):
                    raise SystemExit("missing source text")
                print("Implement a login module for me")
                """,
            )
            config = {"providers": {"translator": self._process_provider(script)}}

            translator = make_text_translator(config, "translator", root / "translation-work")
            translated = translator.translate("帮我实现登录模块", "zh", "en", "task")

            self.assertEqual(translated, "Implement a login module for me")
            self.assertEqual(translator.name, "translator")

    def test_translation_provider_overrides_command_timeout_and_separates_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_script = self._write_script(root, "base.py", "print('wrong provider command')")
            translation_script = self._write_script(
                root,
                "translation.py",
                """
                import sys

                print("translator diagnostic", file=sys.stderr)
                print("Implement the requested feature")
                """,
            )
            config = {
                "language": {
                    "translation_provider_overrides": {
                        "command": [sys.executable, str(translation_script)],
                        "timeout_seconds": 3,
                    }
                },
                "providers": {"translator": self._process_provider(base_script)},
            }
            work_dir = root / "translation-work"

            translator = make_text_translator(config, "translator", work_dir)
            translated = translator.translate("实现需求", "zh", "en", "task")

            self.assertEqual(translated, "Implement the requested feature")
            self.assertEqual(translator.provider_config["timeout_seconds"], 3)
            self.assertEqual(
                (work_dir / "provider.stderr.log").read_text(encoding="utf-8"),
                "translator diagnostic\n",
            )

    @unittest.skipUnless(os.name == "nt", "Windows command launcher behavior")
    def test_windows_cmd_translation_provider_runs_through_script_host(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self._write_script(root, "translate.py", "print('Translated through CMD')")
            launcher = root / "translator.cmd"
            launcher.write_text(
                f'@echo off\r\n"{sys.executable}" "{script}"\r\n',
                encoding="utf-8",
            )
            provider = self._process_provider(script)
            provider["command"] = ["translator"]
            config = {"providers": {"translator": provider}}

            with patch.dict(os.environ, {"PATH": str(root) + os.pathsep + os.environ["PATH"]}):
                translator = make_text_translator(config, "translator", root / "work")

                self.assertEqual(
                    translator.translate("翻译任务", "zh", "en", "task"),
                    "Translated through CMD",
                )

    def test_process_creation_error_becomes_retryable_translation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self._write_script(root, "translate.py", "print('unused')")
            translator = make_text_translator(
                {"providers": {"translator": self._process_provider(script)}},
                "translator",
                root / "work",
            )

            with patch("at_flow.providers.subprocess.Popen", side_effect=PermissionError("denied")):
                with self.assertRaises(TranslationError) as raised:
                    translator.translate("翻译任务", "zh", "en", "task")

            self.assertEqual(raised.exception.code, "translation_process_failed")
            self.assertTrue(raised.exception.retryable)
            self.assertIn("could not start", str(raised.exception))

    @unittest.skipUnless(os.name == "nt", "Windows locale decoding behavior")
    def test_utf8_provider_output_does_not_use_the_windows_system_locale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self._write_script(
                root,
                "utf8.py",
                """
                import sys

                sys.stdout.buffer.write("中文展示产物".encode("utf-8"))
                """,
            )
            translator = make_text_translator(
                {"providers": {"translator": self._process_provider(script)}},
                "translator",
                root / "work",
            )

            self.assertEqual(
                translator.translate("English artifact", "en", "zh", "artifact"),
                "中文展示产物",
            )

    @unittest.skipUnless(os.name == "nt", "Windows process-tree timeout behavior")
    def test_translation_timeout_terminates_the_windows_child_process_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "child-finished.txt"
            child = self._write_script(
                root,
                "child.py",
                f"""
                import time
                from pathlib import Path

                time.sleep(3)
                Path({str(marker)!r}).write_text("still running", encoding="utf-8")
                """,
            )
            launcher = root / "slow-translator.cmd"
            launcher.write_text(
                f'@echo off\r\n"{sys.executable}" "{child}"\r\n',
                encoding="utf-8",
            )
            provider = self._process_provider(child)
            provider.update({"command": [str(launcher)], "timeout_seconds": 1})
            translator = make_text_translator(
                {"providers": {"translator": provider}},
                "translator",
                root / "work",
            )

            started = time.monotonic()
            with self.assertRaises(TranslationError) as raised:
                translator.translate("任务", "zh", "en", "task")
            elapsed = time.monotonic() - started
            time.sleep(3)

            self.assertIn("timed out after 1s", str(raised.exception))
            self.assertLess(elapsed, 2.5)
            self.assertFalse(marker.exists())

    def test_unknown_translation_provider_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TranslationError) as raised:
                make_text_translator({"providers": {}}, "missing", Path(directory))

            self.assertEqual(raised.exception.code, "translation_provider_unavailable")
            self.assertFalse(raised.exception.retryable)

    def test_mock_translation_provider_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = {"providers": {"mock": {"type": "mock"}}}

            with self.assertRaises(TranslationError) as raised:
                make_text_translator(config, "mock", Path(directory))

            self.assertEqual(raised.exception.code, "translation_provider_unavailable")

    def test_non_zero_translation_process_is_retryable_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self._write_script(root, "fail.py", "raise SystemExit('translator offline')")
            translator = make_text_translator(
                {"providers": {"translator": self._process_provider(script)}},
                "translator",
                root / "work",
            )

            with self.assertRaises(TranslationError) as raised:
                translator.translate("任务", "zh", "en", "task")

            self.assertEqual(raised.exception.code, "translation_process_failed")
            self.assertTrue(raised.exception.retryable)
            self.assertNotIn("translator offline", str(raised.exception))
            self.assertIn("stderr logged separately", str(raised.exception))
            self.assertIn(
                "translator offline",
                (root / "work" / "provider.stderr.log").read_text(encoding="utf-8"),
            )

    def test_empty_translation_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self._write_script(root, "empty.py", "print('')")
            translator = make_text_translator(
                {"providers": {"translator": self._process_provider(script)}},
                "translator",
                root / "work",
            )

            with self.assertRaises(TranslationError) as raised:
                translator.translate("任务", "zh", "en", "task")

            self.assertEqual(raised.exception.code, "invalid_translation_output")

    def test_unchanged_translation_output_is_rejected_for_different_languages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self._write_script(
                root,
                "same.py",
                'import sys; sys.stdout.buffer.write("任务".encode("utf-8"))',
            )
            translator = make_text_translator(
                {"providers": {"translator": self._process_provider(script)}},
                "translator",
                root / "work",
            )

            with self.assertRaises(TranslationError) as raised:
                translator.translate("任务", "zh", "en", "task")

            self.assertEqual(raised.exception.code, "invalid_translation_output")

    def test_translation_skill_instructions_are_loaded_into_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self._write_script(
                root,
                "check_skill.py",
                """
                import sys

                data = sys.stdin.buffer.read().decode("utf-8")
                if "Language Translation" not in data:
                    raise SystemExit("missing skill instructions")
                if "handoff" not in data:
                    raise SystemExit("missing glossary")
                if "帮我实现登录模块" not in data:
                    raise SystemExit("missing source text")
                print("Implement a login module for me")
                """,
            )
            skill_dir = root / "skills" / "language-translation"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "# Language Translation\n\nFollow the platform rules exactly.",
                encoding="utf-8",
            )
            (skill_dir / "glossary.md").write_text("handoff: 交接", encoding="utf-8")
            translator = make_text_translator(
                {"providers": {"translator": self._process_provider(script)}},
                "translator",
                root / "work",
                skill_dir=skill_dir,
            )

            translated = translator.translate("帮我实现登录模块", "zh", "en", "task")

            self.assertEqual(translated, "Implement a login module for me")

    def test_missing_translation_skill_raises_typed_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self._write_script(root, "unused.py", "print('unused')")
            translator = make_text_translator(
                {"providers": {"translator": self._process_provider(script)}},
                "translator",
                root / "work",
                skill_dir=root / "missing-skill",
            )

            with self.assertRaises(TranslationError) as raised:
                translator.translate("任务", "zh", "en", "task")

            self.assertEqual(raised.exception.code, "translation_skill_missing")
            self.assertFalse(raised.exception.retryable)

    def _process_provider(self, script: Path) -> dict[str, object]:
        return {
            "type": "process",
            "command": [sys.executable, str(script)],
            "prompt_mode": "stdin",
            "env_policy": "minimal",
            "env_passthrough": ["PATH", "SystemRoot", "TEMP", "TMP"],
            "timeout_seconds": 10,
        }

    def _write_script(self, root: Path, name: str, source: str) -> Path:
        path = root / name
        path.write_text(textwrap.dedent(source).strip() + "\n", encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()

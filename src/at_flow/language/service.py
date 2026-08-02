from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .adapter import build_language_profile
from .schemas import LANGUAGE_SCHEMA_VERSION
from .translator import ProcessTextTranslator, TextTranslator, TranslationError, make_text_translator
from ..models import SessionState, now_iso
from ..workspace import ATWorkspace


class LanguageError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.retryable = retryable


TranslatorFactory = Callable[[dict[str, Any], str, Path], TextTranslator]


class LanguageService:
    def __init__(
        self,
        workspace: ATWorkspace,
        *,
        translator: TextTranslator | None = None,
        translator_factory: TranslatorFactory = make_text_translator,
    ) -> None:
        self.workspace = workspace
        self.translator = translator
        self.translator_factory = translator_factory

    def ensure_runtime_profile(self, session: SessionState) -> dict[str, Any]:
        path = self.workspace.session_dir(session.id) / "language.json"
        profile = self._load_reusable_profile(path, session)
        if profile is None:
            profile = build_language_profile(self.workspace.config, session).to_dict()
            self._write(path, profile)

        input_state = profile["input_translation"]
        status = str(input_state["status"])
        if status in {"disabled", "not_required", "completed"}:
            return profile

        provider_name = str(input_state.get("provider") or "")
        input_state.update({"status": "running", "error": None, "updated_at": now_iso()})
        self._write(path, profile)
        try:
            translator = self.translator or self.translator_factory(
                self.workspace.config,
                provider_name,
                self.workspace.session_dir(session.id) / "translation" / "input",
            )
            self._attach_skill_dir(translator)
            translated = translator.translate(
                str(profile["task_original"]),
                str(profile["source_language"]),
                str(profile["runtime_language"]),
                "task",
            ).strip()
        except TranslationError as exc:
            input_state.update({"status": "failed", "error": str(exc), "updated_at": now_iso()})
            self._write(path, profile)
            raise LanguageError("input_translation_failed", str(exc), retryable=exc.retryable) from exc

        profile["task_runtime"] = translated
        input_state.update(
            {
                "status": "completed",
                "provider": translator.name,
                "error": None,
                "updated_at": now_iso(),
            }
        )
        self._write(path, profile)
        return profile

    def get_profile(self, session: SessionState) -> dict[str, Any]:
        path = self.workspace.session_dir(session.id) / "language.json"
        profile = self._load_reusable_profile(path, session)
        if profile is not None:
            return profile
        return build_language_profile(self.workspace.config, session).to_dict()

    def translate_artifact(self, session: SessionState, agent: str, source_path: Path) -> Path | None:
        profile_path = self.workspace.session_dir(session.id) / "language.json"
        profile = self.get_profile(session)
        state = profile["display_translation"]
        status = str(state["status"])
        if status == "disabled":
            return None

        target = source_path.with_name("artifact.zh.md")
        if status == "not_required":
            target.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
            return target
        if status == "completed" and target.is_file():
            return target

        provider_name = str(state.get("provider") or "")
        state.update({"status": "running", "error": None, "updated_at": now_iso()})
        self._write(profile_path, profile)
        try:
            translator = self.translator or self.translator_factory(
                self.workspace.config,
                provider_name,
                self.workspace.session_dir(session.id) / "translation" / "display" / agent,
            )
            self._attach_skill_dir(translator)
            translated = translator.translate(
                source_path.read_text(encoding="utf-8"),
                str(profile["runtime_language"]),
                str(profile["display_language"]),
                "artifact",
            ).strip()
        except TranslationError as exc:
            state.update({"status": "failed", "error": str(exc), "updated_at": now_iso()})
            self._write(profile_path, profile)
            return None

        target.write_text(translated + "\n", encoding="utf-8")
        state.update(
            {
                "status": "completed",
                "provider": translator.name,
                "error": None,
                "updated_at": now_iso(),
            }
        )
        self._write(profile_path, profile)
        return target

    def _attach_skill_dir(self, translator: TextTranslator) -> None:
        if not isinstance(translator, ProcessTextTranslator):
            return
        translator.skill_dir = (
            self.workspace.shared_root / "skills" / "language-translation"
        )

    def _load_reusable_profile(self, path: Path, session: SessionState) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != LANGUAGE_SCHEMA_VERSION:
            return None
        if data.get("task_original") != session.task:
            return None
        state = data.get("input_translation")
        if not isinstance(state, dict):
            return None
        if state.get("status") == "completed" and not str(data.get("task_runtime") or "").strip():
            return None
        return data

    def _write(self, path: Path, profile: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

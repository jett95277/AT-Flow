from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import LanguageProfile, TranslationState
from ..models import SessionState, now_iso


def build_language_profile(config: dict[str, Any], session: SessionState) -> LanguageProfile:
    language = config.get("language", {})
    if not isinstance(language, dict):
        language = {}
    enabled = bool(language.get("enabled", False))
    configured_source = _language_value(language, "source", _language_value(language, "user", "auto"))
    source_language = detect_source_language(session.task) if configured_source == "auto" else configured_source
    configured_runtime = _language_value(language, "runtime", "en")
    runtime_language = configured_runtime if enabled else source_language
    display_language = _language_value(language, "display", "zh")
    artifact_mode = _language_value(language, "artifact_mode", "bilingual")
    provider = _language_value(language, "translation_provider", "none")
    timestamp = now_iso()

    if not enabled:
        input_status = "disabled"
    elif source_language == runtime_language:
        input_status = "not_required"
    else:
        input_status = "pending"

    translate_artifacts = bool(language.get("translate_artifacts", True))
    if not enabled or not translate_artifacts:
        display_status = "disabled"
    elif runtime_language == display_language:
        display_status = "not_required"
    else:
        display_status = "pending"

    return LanguageProfile(
        source_language=source_language,
        runtime_language=runtime_language,
        display_language=display_language,
        artifact_mode=artifact_mode,
        task_original=session.task,
        task_runtime=session.task if input_status in {"disabled", "not_required"} else "",
        input_translation=TranslationState(input_status, provider if enabled else "none", None, timestamp),
        display_translation=TranslationState(display_status, provider if enabled else "none", None, timestamp),
    )


def ensure_session_language_profile(config: dict[str, Any], session: SessionState, language_path: Path) -> dict[str, Any]:
    language_path.parent.mkdir(parents=True, exist_ok=True)
    if language_path.exists():
        with language_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    profile = build_language_profile(config, session).to_dict()
    language_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return profile


def detect_source_language(text: str) -> str:
    return "zh" if any("\u3400" <= character <= "\u9fff" for character in text) else "en"


def _language_value(language: dict[str, Any], key: str, default: str) -> str:
    value = language.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default

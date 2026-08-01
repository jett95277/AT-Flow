from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import LanguageProfile
from ..models import SessionState


def build_language_profile(config: dict[str, Any], session: SessionState) -> LanguageProfile:
    language = config.get("language", {})
    source_language = _language_value(language, "user", "zh")
    runtime_language = _language_value(language, "runtime", "en")
    display_language = _language_value(language, "display", "zh")
    artifact_mode = _language_value(language, "artifact_mode", "bilingual")
    task_runtime = _runtime_task(session.task, runtime_language)

    return LanguageProfile(
        source_language=source_language,
        runtime_language=runtime_language,
        display_language=display_language,
        artifact_mode=artifact_mode,
        task_original=session.task,
        task_runtime=task_runtime,
        display_summary=session.task,
    )


def ensure_session_language_profile(config: dict[str, Any], session: SessionState, language_path: Path) -> dict[str, Any]:
    language_path.parent.mkdir(parents=True, exist_ok=True)
    if language_path.exists():
        with language_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    profile = build_language_profile(config, session).to_dict()
    language_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return profile


def _language_value(language: Any, key: str, default: str) -> str:
    if isinstance(language, dict):
        value = language.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return default


def _runtime_task(task: str, runtime_language: str) -> str:
    if runtime_language != "en":
        return task
    return "\n".join(
        [
            "Execute this user task in English runtime context.",
            "Keep reasoning instructions and artifact.md in English.",
            "Original user task:",
            task,
        ]
    )

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


LANGUAGE_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class TranslationState:
    status: str
    provider: str
    error: str | None
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "provider": self.provider,
            "error": self.error,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class LanguageProfile:
    source_language: str
    runtime_language: str
    display_language: str
    artifact_mode: str
    task_original: str
    task_runtime: str
    input_translation: TranslationState
    display_translation: TranslationState

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LANGUAGE_SCHEMA_VERSION,
            "source_language": self.source_language,
            "runtime_language": self.runtime_language,
            "display_language": self.display_language,
            "artifact_mode": self.artifact_mode,
            "task_original": self.task_original,
            "task_runtime": self.task_runtime,
            "input_translation": self.input_translation.to_dict(),
            "display_translation": self.display_translation.to_dict(),
        }

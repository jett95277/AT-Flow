from __future__ import annotations

from dataclasses import dataclass
from typing import Any


LANGUAGE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LanguageProfile:
    source_language: str
    runtime_language: str
    display_language: str
    artifact_mode: str
    task_original: str
    task_runtime: str
    display_summary: str
    translation_status: str = "pending"
    translation_provider: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LANGUAGE_SCHEMA_VERSION,
            "source_language": self.source_language,
            "runtime_language": self.runtime_language,
            "display_language": self.display_language,
            "artifact_mode": self.artifact_mode,
            "task_original": self.task_original,
            "task_runtime": self.task_runtime,
            "display_summary": self.display_summary,
            "translation_status": self.translation_status,
            "translation_provider": self.translation_provider,
        }

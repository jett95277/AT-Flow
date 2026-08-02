from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ..providers import ProviderError, run_process_prompt


class TranslationError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class TextTranslator(Protocol):
    name: str

    def translate(self, text: str, source_language: str, target_language: str, purpose: str) -> str:
        ...


class ProcessTextTranslator:
    def __init__(
        self,
        name: str,
        provider_config: dict[str, Any],
        work_dir: Path,
        provider_overrides: dict[str, Any] | None = None,
        skill_dir: Path | None = None,
    ) -> None:
        self.name = name
        self.provider_config = _restricted_config(provider_config, provider_overrides or {})
        self.work_dir = work_dir.resolve()
        self.skill_dir = skill_dir.resolve() if skill_dir else None

    def translate(self, text: str, source_language: str, target_language: str, purpose: str) -> str:
        prompt = self._build_prompt(text, source_language, target_language, purpose)
        try:
            output = run_process_prompt(
                self.name,
                self.provider_config,
                prompt,
                cwd=self.work_dir,
                env_overrides={
                    "AT_TRANSLATION_SOURCE": source_language,
                    "AT_TRANSLATION_TARGET": target_language,
                    "AT_TRANSLATION_PURPOSE": purpose,
                },
                prompt_path=self.work_dir / "prompt.md",
                stderr_path=self.work_dir / "provider.stderr.log",
            ).strip()
        except ProviderError as exc:
            raise TranslationError("translation_process_failed", str(exc), retryable=True) from exc
        if not output or (source_language != target_language and output == text.strip()):
            raise TranslationError(
                "invalid_translation_output",
                "Translation provider returned empty or unchanged output",
                retryable=True,
            )
        return output

    def _build_prompt(
        self, text: str, source_language: str, target_language: str, purpose: str
    ) -> str:
        instructions = self._skill_instructions()
        base = _translation_prompt(text, source_language, target_language, purpose)
        if not instructions:
            return base
        return instructions + "\n\n" + base

    def _skill_instructions(self) -> str:
        if self.skill_dir is None:
            return ""
        skill_file = self.skill_dir / "SKILL.md"
        if not skill_file.is_file():
            raise TranslationError(
                "translation_skill_missing",
                f"Translation skill missing: {skill_file}",
                retryable=False,
            )
        parts = [skill_file.read_text(encoding="utf-8")]
        glossary = self.skill_dir / "glossary.md"
        if glossary.is_file():
            parts.append(glossary.read_text(encoding="utf-8"))
        return "\n\n".join(parts)


def make_text_translator(
    config: dict[str, Any], provider_name: str, work_dir: Path, skill_dir: Path | None = None
) -> TextTranslator:
    providers = config.get("providers", {})
    provider_config = providers.get(provider_name) if isinstance(providers, dict) else None
    if not isinstance(provider_config, dict):
        raise TranslationError(
            "translation_provider_unavailable",
            f"Unknown translation provider: {provider_name or '(empty)'}",
            retryable=False,
        )
    if provider_config.get("type", provider_name) != "process" or not provider_config.get("command"):
        raise TranslationError(
            "translation_provider_unavailable",
            f"Translation provider must be a configured process provider: {provider_name}",
            retryable=False,
        )
    language_config = config.get("language", {})
    overrides = (
        language_config.get("translation_provider_overrides", {})
        if isinstance(language_config, dict)
        else {}
    )
    return ProcessTextTranslator(
        provider_name,
        provider_config,
        work_dir,
        overrides if isinstance(overrides, dict) else {},
        skill_dir=skill_dir,
    )


def _restricted_config(
    provider_config: dict[str, Any], provider_overrides: dict[str, Any]
) -> dict[str, Any]:
    safe = dict(provider_config)
    for key in ("command", "timeout_seconds"):
        if key in provider_overrides:
            safe[key] = provider_overrides[key]
    safe["prompt_mode"] = "stdin"
    safe["env_policy"] = "minimal"
    passthrough = provider_config.get("env_passthrough", [])
    safe["env_passthrough"] = [str(name) for name in passthrough if not str(name).startswith("AT_")]
    safe.pop("env", None)
    safe.pop("cwd", None)
    return safe


def _translation_prompt(text: str, source_language: str, target_language: str, purpose: str) -> str:
    return "\n".join(
        [
            "Translate the following text for the AT language contract.",
            f"Source language: {source_language}",
            f"Target language: {target_language}",
            f"Purpose: {purpose}",
            "Return only the translated text. Do not add commentary or Markdown fences.",
            "Preserve paths, commands, API names, code identifiers, and code blocks exactly.",
            "",
            text,
        ]
    )

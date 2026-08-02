from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Callable

from .errors import ApiError
from .schemas import FileNodeResponse
from ..language.translator import (
    ProcessTextTranslator,
    TextTranslator,
    TranslationError,
    make_text_translator,
)
from ..workspace import ATWorkspace


ALLOWED_TREE_ROOTS = ("agents", "shared", "sessions")


class WorkspaceService:
    def __init__(
        self,
        workspace: ATWorkspace,
        *,
        translator_factory: Callable[[dict[str, Any], str, Path], TextTranslator] = make_text_translator,
    ) -> None:
        self.workspace = workspace
        self.translator_factory = translator_factory

    def tree(self) -> list[FileNodeResponse]:
        nodes: list[FileNodeResponse] = []
        for name, path in self._tree_roots():
            if path.exists():
                excluded_children = (
                    frozenset({"agents"})
                    if name == "shared" and self.workspace.agents_root == (self.workspace.shared_root / "agents").resolve()
                    else frozenset()
                )
                nodes.append(self._node_for_path(path, name, excluded_children))
        return nodes

    def read_file(self, relative_path: str, language: str = "zh") -> str:
        path = self._resolve_allowed_file(relative_path)
        if language == "zh":
            display = self._display_copy(path)
            if display is not None and display.is_file():
                return display.read_text(encoding="utf-8")
            if self._session_document_needs_translation(path):
                return self._translate_session_document(path)
        return path.read_text(encoding="utf-8")

    def _display_copy(self, path: Path) -> Path | None:
        if path.suffix.lower() != ".md":
            return None
        return path.with_name(f"{path.stem}.zh.md")

    def _session_document_needs_translation(self, path: Path) -> bool:
        try:
            path.relative_to(self.workspace.sessions_root)
        except ValueError:
            return False
        if path.suffix.lower() != ".md":
            return False
        language = self.workspace.config.get("language", {})
        if not isinstance(language, dict) or not language.get("enabled"):
            return False
        runtime = str(language.get("runtime") or "en")
        display = str(language.get("display") or "zh")
        if runtime == display:
            return False
        provider = str(language.get("translation_provider") or "")
        return bool(provider)

    def _translate_session_document(self, path: Path) -> str:
        language = self.workspace.config.get("language", {})
        if not isinstance(language, dict):
            language = {}
        provider = str(language.get("translation_provider") or "")
        runtime = str(language.get("runtime") or "en")
        display = str(language.get("display") or "zh")
        work_dir = self.workspace.root / ".at" / "translation" / "workspace"
        try:
            translator = self.translator_factory(self.workspace.config, provider, work_dir)
            self._attach_skill_dir(translator)
            translated = translator.translate(
                path.read_text(encoding="utf-8"),
                runtime,
                display,
                "document",
            ).strip()
        except TranslationError as exc:
            raise ApiError(
                code="display_translation_failed",
                message=str(exc),
                retryable=exc.retryable,
            ) from exc
        display_path = self._display_copy(path)
        if display_path is not None:
            display_path.parent.mkdir(parents=True, exist_ok=True)
            display_path.write_text(translated + "\n", encoding="utf-8")
        return translated + "\n"

    def _attach_skill_dir(self, translator: TextTranslator) -> None:
        if not isinstance(translator, ProcessTextTranslator):
            return
        translator.skill_dir = self.workspace.shared_root / "skills" / "language-translation"

    def _is_translation_copy(self, path: Path) -> bool:
        name = path.name
        if not name.endswith(".zh.md"):
            return False
        return path.with_name(name[: -len(".zh.md")] + ".md").exists()

    def _tree_roots(self) -> list[tuple[str, Path]]:
        return [
            ("agents", self.workspace.agents_root),
            ("shared", self.workspace.shared_root),
            ("sessions", self.workspace.sessions_root),
        ]

    def _node_for_path(
        self,
        path: Path,
        relative_path: str,
        excluded_children: frozenset[str] = frozenset(),
    ) -> FileNodeResponse:
        if path.is_dir():
            children = [
                self._node_for_path(child, f"{relative_path}/{child.name}")
                for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
                if child.name not in excluded_children
                and not self._is_translation_copy(child)
            ]
            return FileNodeResponse(
                name=path.name,
                path=relative_path,
                kind="directory",
                children=children,
            )
        return FileNodeResponse(
            name=path.name,
            path=relative_path,
            kind="file",
            children=[],
        )

    def _resolve_allowed_file(self, relative_path: str) -> Path:
        posix_path = PurePosixPath(relative_path.replace("\\", "/"))
        if posix_path.is_absolute() or ".." in posix_path.parts:
            raise self._file_not_allowed(relative_path)
        if not posix_path.parts or posix_path.parts[0] not in ALLOWED_TREE_ROOTS:
            raise self._file_not_allowed(relative_path)

        root_name = posix_path.parts[0]
        root_path = dict(self._tree_roots())[root_name]
        candidate = (root_path / Path(*posix_path.parts[1:])).resolve()
        try:
            candidate.relative_to(root_path)
        except ValueError as exc:
            raise self._file_not_allowed(relative_path) from exc
        if not candidate.is_file():
            raise self._file_not_allowed(relative_path)
        return candidate

    def _file_not_allowed(self, relative_path: str) -> ApiError:
        return ApiError(
            code="file_not_allowed",
            message=f"File is not allowed: {relative_path}",
            retryable=False,
        )

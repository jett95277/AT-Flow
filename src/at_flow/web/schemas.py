from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class HealthResponse:
    status: Literal["ok"]
    workspace: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "workspace": self.workspace,
        }


@dataclass(frozen=True)
class DoctorCheckResponse:
    name: str
    ok: bool
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class CommandResultResponse:
    ok: bool
    session: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"ok": self.ok}
        if self.session is not None:
            data["session"] = self.session
        return data


@dataclass(frozen=True)
class FileNodeResponse:
    name: str
    path: str
    kind: Literal["directory", "file"]
    children: list["FileNodeResponse"]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
            "kind": self.kind,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(frozen=True)
class ArtifactViewResponse:
    source: str
    display: str | None
    source_language: str
    display_language: str
    display_status: str
    display_provider: str
    display_error: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "display": self.display,
            "source_language": self.source_language,
            "display_language": self.display_language,
            "display_status": self.display_status,
            "display_provider": self.display_provider,
            "display_error": self.display_error,
        }

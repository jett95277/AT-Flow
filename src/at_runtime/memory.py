from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

import yaml


TIER_DIRS = {"short": "memory/short", "medium": "memory/medium", "long": "memory/long"}
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def memory_path(root: Path, uri: str) -> Path:
    parts = uri.split("/")
    # memory://<scope>/<name>/<tier>
    if len(parts) < 5:
        raise ValueError(f"invalid memory uri: {uri}")
    _, _, scope, name, tier = parts[:5]
    if tier not in TIER_DIRS:
        raise ValueError(f"unknown tier: {tier}")
    if not _SAFE_NAME.fullmatch(scope) or not _SAFE_NAME.fullmatch(name):
        raise ValueError(f"invalid memory uri: {uri}")
    return root / ".agent" / TIER_DIRS[tier] / f"{scope}-{name}.md"


def write_memory(
    root: Path,
    uri: str,
    content: str,
    source: dict,
    status: str = "candidate",
) -> dict[str, Any]:
    path = memory_path(root, uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    item = {
        "uri": uri,
        "content": content,
        "status": status,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries = _load_entries(path) if path.exists() else []
    entries.append(item)
    _save_entries(path, entries)
    return item


def read_memory(root: Path, uri: str) -> list[dict[str, Any]]:
    path = memory_path(root, uri)
    return _load_entries(path) if path.exists() else []


def list_memory(root: Path, scope: str, tier: str) -> list[dict[str, Any]]:
    directory = root / ".agent" / TIER_DIRS[tier]
    if not directory.exists():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(directory.glob(f"{scope}-*.md")):
        entries.extend(_load_entries(path))
    return entries


def _load_entries(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    return [
        entry
        for entry in yaml.safe_load_all(text)
        if isinstance(entry, dict)
    ]


def _save_entries(path: Path, entries: list[dict[str, Any]]) -> None:
    path.write_text(
        yaml.safe_dump_all(entries, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

import yaml

from at_runtime.observer import record_event


TIER_DIRS = {"short": "memory/short", "medium": "memory/medium", "long": "memory/long"}
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def memory_path(root: Path, uri: str) -> Path:
    scope, name, tier = _parse_uri(uri)
    return root / ".agent" / TIER_DIRS[tier] / f"{scope}-{name}.md"


def _parse_uri(uri: str) -> tuple[str, str, str]:
    parts = uri.split("/")
    if len(parts) < 5:
        raise ValueError(f"invalid memory uri: {uri}")
    scope, name, tier = parts[2], parts[3], parts[4]
    if tier not in TIER_DIRS:
        raise ValueError(f"unknown tier: {tier}")
    if not _SAFE_NAME.fullmatch(scope) or not _SAFE_NAME.fullmatch(name):
        raise ValueError(f"invalid memory uri: {uri}")
    return scope, name, tier


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


STATUS_NEXT = {"candidate": "active", "active": "verified"}
INACTIVE = {"archived", "deprecated"}


def list_tier_entries(
    root: Path, tier: str, include_all: bool = False
) -> list[dict[str, Any]]:
    directory = root / ".agent" / TIER_DIRS[tier]
    if not directory.exists():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.md")):
        for entry in _load_entries(path):
            if include_all or entry.get("status") not in INACTIVE:
                entries.append(entry)
    return entries


def _cross_tier_target(entry: dict[str, Any], uri: str, to_tier: str) -> str:
    scope, name, _ = _parse_uri(uri)
    source = entry.get("source")
    if not isinstance(source, dict):
        source = {}
    if to_tier == "medium":
        task = source.get("task")
        if not task:
            raise ValueError("缺少 task 归属（source.task），无法提升到 medium")
        return f"memory://task/{task}/medium"
    if to_tier == "long":
        project = source.get("project")
        if not project:
            raise ValueError("缺少 project 归属（source.project），无法提升到 long")
        return f"memory://project/{project}/long"
    raise ValueError(f"unknown target tier: {to_tier}")


def promote_memory(root: Path, uri: str, to_tier: str | None = None) -> dict[str, Any]:
    path = memory_path(root, uri)
    if not path.exists():
        raise FileNotFoundError(f"unknown memory: {uri}")
    entries = _load_entries(path)
    if not entries:
        raise ValueError(f"empty memory: {uri}")
    if to_tier:
        if to_tier not in TIER_DIRS:
            raise ValueError(f"unknown tier: {to_tier}")
        new_uri = _cross_tier_target(entries[-1], uri, to_tier)
        for entry in entries:
            entry["status"] = "verified" if to_tier == "long" else "active"
        new_path = memory_path(root, new_uri)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if new_path.exists():
            entries = _load_entries(new_path) + entries
        _save_entries(new_path, entries)
        path.unlink()
        record_event(root, "memory.promoted", None, {"from": uri, "to": new_uri, "tier": to_tier})
        return entries[-1]
    current = entries[-1]["status"]
    if current not in STATUS_NEXT:
        raise ValueError(f"cannot promote status {current!r}")
    entries[-1]["status"] = STATUS_NEXT[current]
    _save_entries(path, entries)
    record_event(root, "memory.promoted", None, {"uri": uri, "status": entries[-1]["status"]})
    return entries[-1]


def _update_entries(root: Path, uri: str, status: str, event: str) -> dict[str, Any]:
    path = memory_path(root, uri)
    if not path.exists():
        raise FileNotFoundError(f"unknown memory: {uri}")
    entries = _load_entries(path)
    if not entries:
        raise ValueError(f"empty memory: {uri}")
    for entry in entries:
        entry["status"] = status
    _save_entries(path, entries)
    record_event(root, event, None, {"uri": uri, "status": status})
    return entries[-1]


def archive_memory(root: Path, uri: str) -> dict[str, Any]:
    return _update_entries(root, uri, "archived", "memory.archived")


def discard_memory(root: Path, uri: str) -> dict[str, Any]:
    return _update_entries(root, uri, "deprecated", "memory.discarded")


def write_memory_structured(
    root: Path,
    uri: str,
    conclusion: str = "",
    constraints: list[str] | None = None,
    unresolved: list[str] | None = None,
    source: dict | None = None,
) -> dict[str, Any]:
    constraints = constraints or []
    unresolved = unresolved or []
    if not conclusion and not constraints and not unresolved:
        raise ValueError("at least one field required (conclusion/constraints/unresolved)")
    item = {
        "uri": uri,
        "content": conclusion,
        "constraints": constraints,
        "unresolved": unresolved,
        "status": "candidate",
        "source": source or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path = memory_path(root, uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = _load_entries(path) if path.exists() else []
    entries.append(item)
    _save_entries(path, entries)
    record_event(root, "memory.write", None, {"uri": uri, "content_length": len(conclusion)})
    return item


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

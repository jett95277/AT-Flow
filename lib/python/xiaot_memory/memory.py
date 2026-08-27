from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from xiaot_memory.memory_models import (
    LEGACY_STATUS_TO_VALIDITY,
    make_entry,
    parse_uri as _parse_uri,
)
from xiaot_memory.observer import record_event


TIER_DIRS = {"short": "memory/short", "medium": "memory/medium", "long": "memory/long"}


def memory_path(root: Path, uri: str) -> Path:
    scope, name, tier = _parse_uri(uri)
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
    item = make_entry(uri, content, source, status=status)
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


def _resolve_index(entries: list[dict[str, Any]], index: int) -> int:
    if index < 0:
        index = len(entries) + index
    if not 0 <= index < len(entries):
        raise ValueError(
            f"index out of range (available: 0..{len(entries) - 1})"
        )
    return index


def promote_memory(
    root: Path, uri: str, to_tier: str | None = None, index: int = -1, all_: bool = False
) -> dict[str, Any]:
    path = memory_path(root, uri)
    if not path.exists():
        raise FileNotFoundError(f"unknown memory: {uri}")
    entries = _load_entries(path)
    if not entries:
        raise ValueError(f"empty memory: {uri}")
    if to_tier:
        if to_tier not in TIER_DIRS:
            raise ValueError(f"unknown tier: {to_tier}")
        targets = entries if all_ else [entries[_resolve_index(entries, index)]]
        new_uri = _cross_tier_target(targets[-1], uri, to_tier)
        new_path = memory_path(root, new_uri)
        if new_path == path:
            raise ValueError(f"cannot promote {uri}: target uri is identical")
        for entry in targets:
            entry["status"] = "verified" if to_tier == "long" else "active"
            entry["uri"] = new_uri
            entry["tier"] = to_tier
            entry["scope"] = new_uri.split("/")[2]
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if new_path.exists():
            new_entries = _load_entries(new_path) + targets
        else:
            new_entries = targets
        _save_entries(new_path, new_entries)
        if all_:
            path.unlink()
        else:
            resolved = _resolve_index(entries, index)
            remaining = [e for i, e in enumerate(entries) if i != resolved]
            if remaining:
                _save_entries(path, remaining)
            else:
                path.unlink()
        record_event(root, "memory.promoted", None, {"from": uri, "to": new_uri, "tier": to_tier})
        return targets[-1]
    targets = entries if all_ else [entries[_resolve_index(entries, index)]]
    for entry in targets:
        if entry["status"] not in STATUS_NEXT:
            raise ValueError(f"cannot promote status {entry['status']!r}")
    for entry in targets:
        entry["status"] = STATUS_NEXT[entry["status"]]
    _save_entries(path, entries)
    record_event(root, "memory.promoted", None, {"uri": uri, "status": targets[-1]["status"]})
    return targets[-1]


def _update_entries(
    root: Path, uri: str, status: str, event: str, index: int = -1, all_: bool = False
) -> dict[str, Any]:
    path = memory_path(root, uri)
    if not path.exists():
        raise FileNotFoundError(f"unknown memory: {uri}")
    entries = _load_entries(path)
    if not entries:
        raise ValueError(f"empty memory: {uri}")
    targets = entries if all_ else [entries[_resolve_index(entries, index)]]
    # 保留旧 status 语义（archived/deprecated）供旧命令兼容，同时同步新模型 validity。
    validity = LEGACY_STATUS_TO_VALIDITY.get(status)
    for entry in targets:
        entry["status"] = status
        if validity:
            entry["validity"] = validity
    _save_entries(path, entries)
    record_event(root, event, None, {"uri": uri, "status": status})
    return targets[-1]


def archive_memory(
    root: Path, uri: str, index: int = -1, all_: bool = False
) -> dict[str, Any]:
    return _update_entries(root, uri, "archived", "memory.archived", index, all_)


def discard_memory(
    root: Path, uri: str, index: int = -1, all_: bool = False
) -> dict[str, Any]:
    return _update_entries(root, uri, "deprecated", "memory.discarded", index, all_)


def verify_memory(
    root: Path, uri: str, index: int = -1, evidence: list[str] | None = None
) -> dict[str, Any]:
    """机械操作：置 status=verified 并写入证据。由治理层 policy 校验后调用。

    不记录审计事件：统一由 memory_policy 的 request_verify 经 memory_events.log_action
    记录富事件（含 actor/reason），避免同一操作产生重复事件。
    """
    path = memory_path(root, uri)
    if not path.exists():
        raise FileNotFoundError(f"unknown memory: {uri}")
    entries = _load_entries(path)
    if not entries:
        raise ValueError(f"empty memory: {uri}")
    resolved = _resolve_index(entries, index)
    entry = entries[resolved]
    entry["status"] = "verified"
    if evidence:
        entry["evidence"] = list(evidence)
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_entries(path, entries)
    return entry


def supersede_memory(
    root: Path,
    uri: str,
    index: int = -1,
    *,
    supersedes_id: str | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    """机械操作：置 validity=superseded。由治理层 policy 校验确认后调用。

    不记录审计事件：统一由 memory_policy 的 request_supersede / write_entry 经
    memory_events.log_action 记录，避免重复事件。
    """
    if not confirmed:
        raise ValueError("supersede requires confirmation")
    path = memory_path(root, uri)
    if not path.exists():
        raise FileNotFoundError(f"unknown memory: {uri}")
    entries = _load_entries(path)
    if not entries:
        raise ValueError(f"empty memory: {uri}")
    resolved = _resolve_index(entries, index)
    entry = entries[resolved]
    entry["validity"] = "superseded"
    if supersedes_id:
        entry["supersedes_id"] = supersedes_id
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_entries(path, entries)
    return entry


def mark_conflicted(
    root: Path, uri: str, index: int = -1, *, confirmed: bool = False
) -> dict[str, Any]:
    """机械操作：置 status=conflicted。由治理层 policy 校验确认后调用。

    不记录审计事件：统一由 memory_policy 的 request_conflict 经 memory_events.log_action
    记录，避免重复事件。
    """
    if not confirmed:
        raise ValueError("conflict requires confirmation")
    path = memory_path(root, uri)
    if not path.exists():
        raise FileNotFoundError(f"unknown memory: {uri}")
    entries = _load_entries(path)
    if not entries:
        raise ValueError(f"empty memory: {uri}")
    resolved = _resolve_index(entries, index)
    entry = entries[resolved]
    entry["status"] = "conflicted"
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_entries(path, entries)
    return entry


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
    source = source or {}
    # Session 记忆必须带 task 归属：session -> medium 的 promote 依赖 source.task
    # （issue-1：无归属写入后无法提升，导致记忆滞留 short 层）
    if _parse_uri(uri)[0] == "session" and not source.get("task"):
        raise ValueError(
            "session 记忆必须带 --task 归属（promote 到 medium 需要）。修复命令：\n"
            f'  at memory write {uri} --conclusion "<结论>" --task <task-id>'
        )
    item = make_entry(
        uri,
        conclusion,
        source,
        status="candidate",
        constraints=constraints,
        unresolved=unresolved,
    )
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
    # issue-4：原子写入（临时文件 + rename），降低并发 read-modify-write 覆盖风险。
    # 注：非全量并发安全（无文件锁），串行约束见 AGENTS.md「记忆约定」。
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump_all(entries, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    tmp.replace(path)

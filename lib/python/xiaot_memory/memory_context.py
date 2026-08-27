"""记忆上下文组装：三分区过滤、作用域优先级与可注入判定（纯函数 + 读取）。

上下文规则（任务书 §5/§6）：
- 可注入三分区：active+current / verified+current / candidate+current。
- conflicted / superseded / archived / discarded 不注入。
- 同内容多作用域按 task>project>global 取最高优先级；candidate 不覆盖 active/verified。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from xiaot_memory.memory import read_memory
from xiaot_memory.memory_models import hydrate_entry

INJECTABLE_STATUS = {"candidate", "active", "verified"}
SCOPE_PRIORITY = {"task": 0, "project": 1, "global": 2}


def is_injectable(entry: dict[str, Any]) -> bool:
    """三分区判定：validity=current 且 status ∈ {candidate, active, verified}。"""
    h = hydrate_entry(entry)
    if h.get("status") == "conflicted":
        return False
    return h.get("validity") in (None, "current") and h.get("status") in INJECTABLE_STATUS


def filter_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按三分区过滤，返回可注入条目的原始 dict 列表。"""
    return [e for e in entries if is_injectable(e)]


def resolve_scope_precedence(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同内容去重：按 task>project>global 取最高优先级；candidate 排在非 candidate 之后。

    返回可能少于输入（同内容保留一条），无内容条目原样保留。
    """
    hydrated = [(e, hydrate_entry(e)) for e in entries]
    groups: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    no_content: list[dict[str, Any]] = []
    for e, h in hydrated:
        content = (h.get("content") or "").strip()
        if content:
            groups.setdefault(content, []).append((e, h))
        else:
            no_content.append(e)
    result: list[dict[str, Any]] = list(no_content)

    def _key(item: tuple[dict[str, Any], dict[str, Any]]) -> tuple[int, int]:
        _e, h = item
        cand = 1 if h.get("status") == "candidate" else 0
        return (cand, SCOPE_PRIORITY.get(h.get("scope"), 99))

    for group in groups.values():
        if len(group) == 1:
            result.append(group[0][0])
        else:
            group.sort(key=_key)
            result.append(group[0][0])
    return result


def injectable_uris(root: Path, uris: list[str]) -> list[str]:
    """返回其中至少有一条可注入 entry 的 uri。"""
    return [uri for uri in uris if filter_entries(read_memory(root, uri))]


def build_memory_context(root: Path, uris: list[str]) -> dict[str, Any]:
    """组装 memory 上下文：过滤后可注入 uris + 每 uri 的（优先级已解析）条目。

    返回 {uris, entries, filtered}；filtered 为无有效 entry 的 uri（不注入）。
    """
    injectable: list[str] = []
    entries: dict[str, list[dict[str, Any]]] = {}
    filtered: list[str] = []
    for uri in uris:
        kept = resolve_scope_precedence(filter_entries(read_memory(root, uri)))
        if kept:
            injectable.append(uri)
            entries[uri] = kept
        else:
            filtered.append(uri)
    return {"uris": injectable, "entries": entries, "filtered": filtered}

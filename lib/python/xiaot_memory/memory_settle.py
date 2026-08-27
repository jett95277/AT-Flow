"""short 任务结算：扫描、分类、默认 dry-run，apply 仅自动归档。

结算规则（任务书 §9）：
- unresolved 保留 short。
- 已完成任务中的纯过程记录可归档（确定性执行）。
- 有明确 supersedes_id 且已确认，可替代旧记录。
- 提升、discard 和冲突确认不自动执行（需用户确认）。
- LLM 可以提炼晋升文本，但不能直接写入正式记忆。
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from xiaot_memory.memory import (
    archive_memory,
    discard_memory,
    list_tier_entries,
    mark_conflicted,
    read_memory,
)
from xiaot_memory.memory_events import log_action
from xiaot_memory.memory_models import hydrate_entry


def collect_task_short(root: Path, task_id: str) -> list[dict[str, Any]]:
    """扫描某个 task 的全部 short 条目（原始条目，未水合）。"""
    result = []
    for entry in list_tier_entries(root, "short", include_all=True):
        h = hydrate_entry(entry)
        if h.get("task_id") == task_id or (entry.get("source") or {}).get("task") == task_id:
            result.append(entry)
    return result


def is_process_info(entry: dict[str, Any]) -> bool:
    """确定性启发式：纯过程信息（kind=process，或空内容无约束无未决）。

    宁可少归档不误删：拿不准返回 False。
    """
    h = hydrate_entry(entry)
    if h.get("kind") == "process":
        return True
    content = (h.get("content") or "").strip()
    constraints = [c for c in (h.get("constraints") or []) if c]
    unresolved = [u for u in (h.get("unresolved") or []) if u]
    if not content and not constraints and not unresolved:
        return True
    return False


def classify_entries(
    entries: list[dict[str, Any]], *, task_completed: bool = True
) -> dict[str, list[dict[str, Any]]]:
    """把条目分类为 keep / auto_archive / suggest_promote / suggest_discard / conflict_candidates。"""
    hydrated = [hydrate_entry(e) for e in entries]
    content_counts = Counter(
        (h.get("content") or "").strip() for h in hydrated if (h.get("content") or "").strip()
    )
    keep: list[dict[str, Any]] = []
    auto_archive: list[dict[str, Any]] = []
    suggest_promote: list[dict[str, Any]] = []
    suggest_discard: list[dict[str, Any]] = []
    conflict_candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry, h in zip(entries, hydrated):
        content = (h.get("content") or "").strip()
        if h.get("validity") in ("archived", "discarded", "superseded"):
            keep.append(entry)
            continue
        if h.get("status") == "conflicted":
            conflict_candidates.append(entry)
            continue
        if h.get("unresolved"):
            keep.append(entry)
            continue
        # 明确重复：同一内容出现多次，非首次的视为候选 discard
        if content and content_counts[content] > 1 and content in seen:
            suggest_discard.append(entry)
            continue
        seen.add(content)
        if h.get("status") == "verified" and (h.get("evidence") or []):
            suggest_promote.append(entry)
            continue
        if task_completed and is_process_info(entry):
            auto_archive.append(entry)
            continue
        keep.append(entry)
    return {
        "keep": keep,
        "auto_archive": auto_archive,
        "suggest_promote": suggest_promote,
        "suggest_discard": suggest_discard,
        "conflict_candidates": conflict_candidates,
    }


def _index_of(entries: list[dict[str, Any]], entry: dict[str, Any]) -> int:
    eid = entry.get("id")
    created = entry.get("created_at")
    for i, cand in enumerate(entries):
        if eid and cand.get("id") == eid:
            return i
        if created and cand.get("created_at") == created:
            return i
    return -1


def _ids(entries: list[dict[str, Any]]) -> list[str]:
    return [e.get("id") or hydrate_entry(e).get("id") for e in entries]


def settle_task(
    root: Path, task_id: str, *, dry_run: bool = True, task_completed: bool = True
) -> dict[str, Any]:
    """结算一个 task 的 short。默认 dry-run 只输出分类，apply 仅自动归档。"""
    entries = collect_task_short(root, task_id)
    classified = classify_entries(entries, task_completed=task_completed)
    if dry_run:
        return {
            "task_id": task_id,
            "dry_run": True,
            "keep": _ids(classified["keep"]),
            "auto_archive": _ids(classified["auto_archive"]),
            "suggest_promote": _ids(classified["suggest_promote"]),
            "suggest_discard": _ids(classified["suggest_discard"]),
            "conflict_candidates": _ids(classified["conflict_candidates"]),
        }
    # apply：仅自动归档纯过程记录；promote/discard/conflict 不自动执行
    archived: list[str] = []
    for entry in classified["auto_archive"]:
        uri = entry["uri"]
        uri_entries = read_memory(root, uri)
        idx = _index_of(uri_entries, entry)
        if idx >= 0:
            result = archive_memory(root, uri, index=idx)
            archived.append(result.get("id") or hydrate_entry(result).get("id"))
    log_action(root, "settle", None, actor="user", reason=f"settle task {task_id}",
               data={"task_id": task_id, "archived": archived})
    return {
        "task_id": task_id,
        "dry_run": False,
        "auto_archived": archived,
        "suggest_promote": _ids(classified["suggest_promote"]),
        "suggest_discard": _ids(classified["suggest_discard"]),
        "conflict_candidates": _ids(classified["conflict_candidates"]),
        "keep": _ids(classified["keep"]),
    }


def apply_confirmed(
    root: Path, task_id: str, *, discard_ids: list[str] | None = None,
    conflict_ids: list[str] | None = None,
) -> dict[str, Any]:
    """用户在 dry-run 输出上确认后，执行 discard / conflict（需 --confirmed 语义）。

    promote 需要重新提炼文本，请走 `at memory promote --confirmed --distilled`，
    不在此自动执行（任务书 §9：LLM 可提炼但不直接写正式记忆）。
    """
    entries = collect_task_short(root, task_id)
    by_id = {hydrate_entry(e).get("id"): e for e in entries}
    discarded: list[str] = []
    conflicted: list[str] = []
    for eid in discard_ids or []:
        entry = by_id.get(eid)
        if not entry:
            continue
        uri = entry["uri"]
        uri_entries = read_memory(root, uri)
        idx = _index_of(uri_entries, entry)
        if idx >= 0:
            discard_memory(root, uri, index=idx)
            discarded.append(eid)
            log_action(root, "discard", eid, actor="user",
                       reason="settle apply_confirmed", data={"uri": uri})
    for eid in conflict_ids or []:
        entry = by_id.get(eid)
        if not entry:
            continue
        uri = entry["uri"]
        uri_entries = read_memory(root, uri)
        idx = _index_of(uri_entries, entry)
        if idx >= 0:
            mark_conflicted(root, uri, index=idx, confirmed=True)
            conflicted.append(eid)
            log_action(root, "conflict", eid, actor="user",
                       reason="settle apply_confirmed", data={"uri": uri})
    log_action(root, "settle", None, actor="user",
               reason=f"apply_confirmed task {task_id}",
               data={"task_id": task_id, "discarded": discarded, "conflicted": conflicted})
    return {"task_id": task_id, "discarded": discarded, "conflicted": conflicted}

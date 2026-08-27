"""普通 JSONL 操作日志（排查与审计用，非事件溯源）。

把任务书 §8 的 action 形态（action/memory_id/from/to/actor/reason/timestamp）
映射到现有 `.agent/runtime/events/events.jsonl`，复用 observer.record_event
的原子 append，不引入新文件格式。新增事件名：memory.verify / memory.supersede /
memory.conflict / memory.settle；保留旧事件名（memory.write/promoted/archived/
discarded/checkpoint/rollback）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from xiaot_memory.observer import list_events, record_event

ACTION_EVENTS = {
    "create",
    "verify",
    "promote",
    "archive",
    "supersede",
    "discard",
    "conflict",
    "settle",
}


def log_action(
    root: Path,
    action: str,
    memory_id: str | None,
    *,
    from_tier: str | None = None,
    to_tier: str | None = None,
    actor: str = "user",
    reason: str = "",
    data: dict[str, Any] | None = None,
) -> None:
    """记录一次治理操作（action ∈ ACTION_EVENTS）。"""
    payload: dict[str, Any] = {
        "memory_id": memory_id,
        "actor": actor,
        "reason": reason,
    }
    if from_tier:
        payload["from"] = from_tier
    if to_tier:
        payload["to"] = to_tier
    if data:
        payload.update(data)
    record_event(root, f"memory.{action}", None, payload)


def list_actions(root: Path, limit: int = 50) -> list[dict[str, Any]]:
    """列出 memory.* 审计事件（默认最近 50 条）。"""
    events = list_events(root, limit=limit * 4)
    return [e for e in events if str(e.get("event", "")).startswith("memory.")][-limit:]

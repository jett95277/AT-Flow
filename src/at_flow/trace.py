from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import now_iso


def append_trace_event(
    trace_path: Path,
    event: str,
    *,
    session_id: str,
    agent: str | None = None,
    step_index: int | None = None,
    status: str | None = None,
    detail: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": now_iso(),
        "event": event,
        "session_id": session_id,
        "agent": agent,
        "step_index": step_index,
        "status": status,
        "detail": detail,
        "data": data or {},
    }
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_trace_events(trace_path: Path) -> list[dict[str, Any]]:
    if not trace_path.exists():
        return []
    events: list[dict[str, Any]] = []
    with trace_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events

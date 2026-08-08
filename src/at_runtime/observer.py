from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def record_event(
    root: Path,
    event: str,
    session: str | None,
    data: dict[str, Any] | None = None,
) -> None:
    path = root / ".agent/runtime/events/events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "event": event,
        "session": session,
        "data": data or {},
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def list_events(root: Path, limit: int = 50) -> list[dict[str, Any]]:
    path = root / ".agent/runtime/events/events.jsonl"
    if not path.exists():
        return []
    events = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events[-limit:]

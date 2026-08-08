from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def create_handoff(
    root: Path,
    handoff_id: str,
    from_role: str,
    to_role: str,
    task_id: str,
    data: dict,
) -> dict[str, Any]:
    handoff = {
        "id": handoff_id,
        "from": from_role,
        "to": to_role,
        "task": task_id,
        **data,
    }
    path = root / ".agent/handoffs" / f"{handoff_id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(handoff, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return handoff


def get_handoff(root: Path, handoff_id: str) -> dict[str, Any]:
    path = root / ".agent/handoffs" / f"{handoff_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"unknown handoff: {handoff_id}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

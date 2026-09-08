"""Orchestration timeline (M5a): checkpoint workspace + memory snapshot.

checkpoint captures a task's in-flight state at a key node (start /
milestone / finish): workspace copy + memory checkpoint reference. rollback
restores the task workspace from a snapshot; memory rollback stays a manual
engine action (A model: memory changes are human-approved, so auto-rollback
of memory is NOT performed here).
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9_-]+", "-", text.lower()).strip("-")
    return s or "node"


def _tl_dir(root: Path) -> Path:
    d = root / ".xiaot" / "timeline"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _node_dir(root: Path, node_id: str) -> Path:
    return _tl_dir(root) / node_id


def checkpoint(root: Path, task_id: str, label: str | None = None) -> dict[str, Any]:
    """Snapshot task workspace + memory at a key node."""
    from xiaot import workspace as ws

    wdir = ws.workspace_dir(root, task_id)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    node_id = f"{ts}-{_slug(label or task_id)}"
    dest = _node_dir(root, node_id)
    # 1) workspace copy
    shutil.copytree(wdir, dest / "workspace")
    # 2) memory checkpoint via existing engine (A model keeps engine untouched)
    memory_node = None
    memory_warning = None
    try:
        from xiaot_memory.timeline import create_checkpoint
        memory_node = create_checkpoint(root, f"orch-{label or task_id}")["id"]
    except Exception as exc:  # noqa: BLE001 - surface, never silent
        memory_warning = f"memory checkpoint failed: {exc}"
    meta = {
        "id": node_id,
        "task_id": task_id,
        "label": label or task_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "memory_node": memory_node,
        "memory_warning": memory_warning,
        "workspace_dir": str(dest / "workspace"),
    }
    (dest / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def list_nodes(root: Path) -> list[dict[str, Any]]:
    d = _tl_dir(root)
    nodes = []
    for p in sorted(d.glob("*/meta.json"), reverse=True):
        try:
            nodes.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return nodes


def rollback(root: Path, node_id: str) -> dict[str, Any]:
    """Restore task workspace from a snapshot node."""
    from xiaot import workspace as ws

    node = _node_dir(root, node_id)
    if not node.exists():
        return {"ok": False, "error": f"timeline node {node_id} not found"}
    meta = json.loads((node / "meta.json").read_text(encoding="utf-8"))
    task_id = meta["task_id"]
    src = node / "workspace"
    if not src.exists():
        return {"ok": False, "error": f"node {node_id} has no workspace snapshot"}
    target = ws.workspace_dir(root, task_id)
    # replace workspace content (not delete unrelated dirs)
    for item in target.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    shutil.copytree(src, target, dirs_exist_ok=True)
    return {"ok": True, "node_id": node_id, "task_id": task_id,
            "restored": str(target),
            "note": "memory rollback is manual (A model: human-approved changes)"}

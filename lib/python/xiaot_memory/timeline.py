from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
from typing import Any

import yaml

from xiaot_memory.memory import TIER_DIRS, list_tier_entries
from xiaot_memory.observer import record_event


def _safe_label(label: str) -> str:
    safe = re.sub(r"[^a-z0-9_-]+", "-", label.lower()).strip("-")
    return safe or "checkpoint"


def create_checkpoint(root: Path, label: str) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    node_id = f"{ts}-{_safe_label(label)}"
    node_dir = root / ".agent/timeline" / node_id
    memory_dir = node_dir / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    tier_counts: dict[str, int] = {}
    for tier, relative in TIER_DIRS.items():
        source = root / ".agent" / relative
        if source.exists():
            shutil.copytree(source, memory_dir / tier)
            # issue-3：与 stats 口径一致，按文件内 entry 数统计，而非 .md 文件数
            tier_counts[tier] = len(list_tier_entries(root, tier, include_all=True))
    meta = {
        "id": node_id,
        "label": label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tiers": tier_counts,
    }
    (node_dir / "meta.yaml").write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    record_event(root, "memory.checkpoint", None, {"node": node_id})
    return meta


def list_checkpoints(root: Path) -> list[dict[str, Any]]:
    directory = root / ".agent/timeline"
    if not directory.exists():
        return []
    nodes = []
    for path in sorted(directory.glob("*/meta.yaml"), reverse=True):
        nodes.append(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return nodes


def rollback_memory(root: Path, node_id: str) -> dict[str, Any]:
    node_dir = root / ".agent/timeline" / node_id
    if not node_dir.exists():
        raise FileNotFoundError(f"unknown checkpoint: {node_id}")
    create_checkpoint(root, f"pre-rollback-{node_id}")
    for tier, relative in TIER_DIRS.items():
        target = root / ".agent" / relative
        target.mkdir(parents=True, exist_ok=True)
        for path in target.glob("*"):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        source = node_dir / "memory" / tier
        if source.exists():
            shutil.copytree(source, target, dirs_exist_ok=True)
    record_event(root, "memory.rollback", None, {"node": node_id})
    return {"node": node_id, "rolled_back": True}

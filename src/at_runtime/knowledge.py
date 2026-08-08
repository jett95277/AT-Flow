from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def propose_knowledge(root: Path, topic: str, content: str, source: dict) -> dict:
    safe = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    ref = f"wiki://{safe}"
    entry = {
        "ref": ref,
        "topic": topic,
        "content": content,
        "source": source,
        "status": "candidate",
    }
    path = root / ".agent/knowledge/refs" / f"{safe}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(entry, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return entry


def query_knowledge(root: Path, topic: str) -> list[dict[str, Any]]:
    directory = root / ".agent/knowledge/refs"
    if not directory.exists():
        return []
    results = []
    for path in sorted(directory.glob("*.yaml")):
        entry = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if topic.lower() in entry.get("topic", "").lower():
            results.append(entry)
    return results


def get_knowledge(root: Path, ref: str) -> dict[str, Any] | None:
    name = ref.split("//")[-1]
    path = root / ".agent/knowledge/refs" / f"{name}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from xiaot_memory.memory import list_tier_entries


def render_memory_tree(root: Path, include_all: bool = False) -> str:
    lines = ["memory"]
    for index, tier in enumerate(("short", "medium", "long")):
        branch = "└──" if index == 2 else "├──"
        lines.append(f"{branch} {tier}")
        entries = list_tier_entries(root, tier, include_all=include_all)
        if tier == "short" and not include_all:
            scopes = {entry.get("uri", "").split("/")[2] for entry in entries}
            lines.append(f"│   └── ({len(scopes)} scopes, {len(entries)} entries)")
            continue
        by_name: dict[str, list[dict]] = {}
        for entry in entries:
            parts = entry.get("uri", "").split("/")
            name = f"{parts[2]}-{parts[3]}" if len(parts) >= 5 else "unknown"
            by_name.setdefault(name, []).append(entry)
        for name_index, (name, name_entries) in enumerate(sorted(by_name.items())):
            name_branch = "└──" if name_index == len(by_name) - 1 else "├──"
            lines.append(f"│   {name_branch} {name}")
            for entry in name_entries:
                status = entry.get("status", "candidate")
                content = (entry.get("content", "") or "").splitlines()[0][:50]
                created = entry.get("created_at", "")[:16]
                lines.append(f"│   │   └── [{status}] {content} · {created}")
    return "\n".join(lines)


def render_memory_export(root: Path, include_all: bool = False) -> str:
    lines = [
        "# AT Memory Export",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for tier in ("short", "medium", "long"):
        lines.append(f"## {tier}")
        lines.append("")
        entries = list_tier_entries(root, tier, include_all=include_all)
        by_name: dict[str, list[dict]] = {}
        for entry in entries:
            parts = entry.get("uri", "").split("/")
            name = f"{parts[2]}-{parts[3]}" if len(parts) >= 5 else "unknown"
            by_name.setdefault(name, []).append(entry)
        if not by_name:
            lines.append("_(empty)_")
            lines.append("")
            continue
        for name, name_entries in sorted(by_name.items()):
            lines.append(f"### {name}")
            for entry in name_entries:
                status = entry.get("status", "candidate")
                content = entry.get("content", "") or ""
                lines.append(f"- [{status}] {content}")
                for label, key in (("Constraints", "constraints"),
                                   ("Unresolved", "unresolved")):
                    items = entry.get(key) or []
                    if items:
                        lines.append(f"  {label}:")
                        for item in items:
                            lines.append(f"    - {item}")
                source = entry.get("source") or {}
                created = entry.get("created_at", "")
                lines.append(f"  Source: {source} | Created: {created}")
            lines.append("")
        lines.append("")
    return "\n".join(lines)


def render_memory_stats(root: Path, include_all: bool = False) -> dict:
    from xiaot_memory.timeline import list_checkpoints

    statuses = ("candidate", "active", "archived", "deprecated")
    tiers: dict[str, dict[str, int]] = {}
    total = 0
    for tier in ("short", "medium", "long"):
        entries = list_tier_entries(root, tier, include_all=include_all)
        counts = {status: 0 for status in statuses}
        for entry in entries:
            status = entry.get("status", "candidate")
            counts[status if status in counts else "candidate"] += 1
        counts["total"] = len(entries)
        tiers[tier] = counts
        total += len(entries)
    return {"tiers": tiers, "total": total, "checkpoints": len(list_checkpoints(root))}

from __future__ import annotations

from pathlib import Path

from at_runtime.memory import list_tier_entries


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

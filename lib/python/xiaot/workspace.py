"""Task workspace management (M1).

`.xiaot/workspace/<task-id>/` holds in-flight task state: plan.md (full plan
document), result.md (outcome), context.json (context snapshot). Workspace is
the resume source and is kept separate from the memory store (.agent/).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any


def xiaot_root(root: Path) -> Path:
    """Project orchestration root (.xiaot), created on demand."""
    d = root / ".xiaot"
    d.mkdir(parents=True, exist_ok=True)
    return d


def workspace_dir(root: Path, task_id: str) -> Path:
    """Return (and create) workspace dir for a task."""
    w = xiaot_root(root) / "workspace" / task_id
    w.mkdir(parents=True, exist_ok=True)
    return w


def workspace_exists(root: Path, task_id: str) -> bool:
    return (xiaot_root(root) / "workspace" / task_id).exists()


def write_plan(root: Path, task_id: str, plan: dict[str, Any]) -> Path:
    """Write plan.md (full markdown plan document) + plan.json snapshot."""
    w = workspace_dir(root, task_id)
    lines = [
        f"# Plan: {plan.get('title', task_id)}",
        "",
        "## Goal",
        plan.get("goal", ""),
        "",
        "## Steps",
    ]
    for i, step in enumerate(plan.get("steps", []), 1):
        lines.append(f"{i}. {step}")
    if plan.get("acceptance"):
        lines += ["", "## Acceptance", plan["acceptance"]]
    path = w / "plan.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    (w / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def write_result(root: Path, task_id: str, status: str, output: str) -> Path:
    """Write result.md outcome summary."""
    w = workspace_dir(root, task_id)
    path = w / "result.md"
    path.write_text(
        f"# Result: {task_id}\n\n- status: {status}\n- output: {output}\n",
        encoding="utf-8",
    )
    return path


def write_context_snapshot(root: Path, task_id: str, context: dict[str, Any]) -> Path:
    """Persist context snapshot (auditable / replayable)."""
    w = workspace_dir(root, task_id)
    path = w / "context.json"
    path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_workspace(root: Path, task_id: str) -> dict[str, Any]:
    """Read task state for resume: plan.json + result + context if present."""
    w = xiaot_root(root) / "workspace" / task_id
    state: dict[str, Any] = {"task_id": task_id, "dir": str(w)}
    for name in ("plan.json", "context.json"):
        p = w / name
        if p.exists():
            state[name[:-5]] = json.loads(p.read_text(encoding="utf-8"))
    r = w / "result.md"
    state["has_result"] = r.exists()
    return state


def list_workspaces(root: Path) -> list[str]:
    d = xiaot_root(root) / "workspace"
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.exists() else []

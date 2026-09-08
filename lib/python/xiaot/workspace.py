"""Task workspace management (M1).

`.xiaot/workspace/<task-id>/` holds in-flight task state: plan.md (full plan
document), result.md (outcome), context.json (context snapshot). Workspace is
the resume source and is kept separate from the memory store (.agent/).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# task ids are embedded in a filesystem path (.xiaot/workspace/<id>/); reject
# anything that could escape the task directory (path separators, "..", dots).
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _check_task_id(task_id: str) -> None:
    if not isinstance(task_id, str) or not _TASK_ID_RE.match(task_id):
        raise ValueError(
            f"invalid task id {task_id!r}: must match {_TASK_ID_RE.pattern!r}")


def xiaot_root(root: Path) -> Path:
    """Project orchestration root (.xiaot), created on demand."""
    d = root / ".xiaot"
    d.mkdir(parents=True, exist_ok=True)
    return d


def workspace_dir(root: Path, task_id: str) -> Path:
    """Return (and create) workspace dir for a task."""
    _check_task_id(task_id)
    w = xiaot_root(root) / "workspace" / task_id
    w.mkdir(parents=True, exist_ok=True)
    return w


def workspace_exists(root: Path, task_id: str) -> bool:
    _check_task_id(task_id)
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
    _check_task_id(task_id)
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


_PROJECT_NAME_FILE = "project.json"


def read_result_status(root: Path, task_id: str) -> str | None:
    """Read the outcome status from result.md (- status: <value>).

    Single read point for the result.md line format (writer is write_result);
    parse errors return None rather than raising.
    """
    _check_task_id(task_id)
    p = xiaot_root(root) / "workspace" / task_id / "result.md"
    if not p.exists():
        return None
    try:
        text = p.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.strip().startswith("- status:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        return None
    return None


def write_project_name(root: Path, name: str) -> Path:
    """Persist the canonical project name (.xiaot/project.json).

    Cross-session memory injection keys on the project name; pinning it once
    (at `xiaot init`) stops drift where different sessions use slightly
    different names and never see each other's memory.
    """
    p = xiaot_root(root) / _PROJECT_NAME_FILE
    p.write_text(json.dumps({"name": name}, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    return p


def read_project_name(root: Path) -> str | None:
    """Read the pinned project name; None when never initialized."""
    p = xiaot_root(root) / _PROJECT_NAME_FILE
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        name = data.get("name")
        return str(name) if name else None
    except Exception:
        return None

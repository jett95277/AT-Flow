from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def create_task(root: Path, task_id: str, goal: str, scope: dict) -> dict:
    task = {
        "id": task_id,
        "goal": goal,
        "scope": scope,
        "status": "created",
        "sessions": [],
    }
    _write_yaml(root / ".agent/runtime/tasks" / f"{task_id}.yaml", task)
    return task


def create_session(
    root: Path, session_id: str, task_id: str, role: str, provider: str
) -> dict:
    session = {
        "id": session_id,
        "task_id": task_id,
        "role": role,
        "provider": provider,
        "status": "created",
        "parent": None,
    }
    _write_yaml(root / ".agent/runtime/sessions" / f"{session_id}.yaml", session)
    task_path = root / ".agent/runtime/tasks" / f"{task_id}.yaml"
    if task_path.exists():
        task = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
        task.setdefault("sessions", []).append(session_id)
        _write_yaml(task_path, task)
    return session


def get_session(root: Path, session_id: str) -> dict[str, Any]:
    path = root / ".agent/runtime/sessions" / f"{session_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"unknown session: {session_id}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def update_session_status(root: Path, session_id: str, status: str) -> dict[str, Any]:
    session = get_session(root, session_id)
    session["status"] = status
    _write_yaml(root / ".agent/runtime/sessions" / f"{session_id}.yaml", session)
    return session


def list_sessions(root: Path) -> list[dict[str, Any]]:
    directory = root / ".agent/runtime/sessions"
    if not directory.exists():
        return []
    return [
        yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for path in sorted(directory.glob("*.yaml"))
    ]

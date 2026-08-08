from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from at_runtime.context import build_context, estimate_tokens
from at_runtime.execution import LocalAdapter
from at_runtime.handoff import create_handoff
from at_runtime.observer import record_event
from at_runtime.registry import create_session, create_task, update_session_status


def run_task_flow(
    root: Path,
    task_id: str,
    goal: str,
    refs: dict,
    provider: str = "mock",
) -> list[dict[str, Any]]:
    create_task(root, task_id, goal, refs.get("scope", {}))
    roles = ["analysis", "code", "test"]
    previous_handoff = None
    steps: list[dict[str, Any]] = []
    for index, role in enumerate(roles):
        session_id = f"{role}-{task_id}-01"
        create_session(root, session_id, task_id, role, provider)
        update_session_status(root, session_id, "running")
        record_event(root, "session.created", session_id, {"role": role})
        handoff_refs = {"handoff": previous_handoff} if previous_handoff else {}
        bundle = build_context(root, session_id, {**refs, **handoff_refs})
        record_event(
            root,
            "context.injected",
            session_id,
            {"tokens": estimate_tokens(json.dumps(bundle, ensure_ascii=False))},
        )
        if provider == "mock":
            output = f"mock {role} output for {task_id}"
        else:
            adapter = LocalAdapter()
            try:
                output = adapter.spawn(bundle, role, root)
            except Exception:
                update_session_status(root, session_id, "failed")
                record_event(root, "session.failed", session_id, {"role": role})
                raise
        if index < len(roles) - 1:
            next_role = roles[index + 1]
            handoff_id = f"H-{task_id}-{role[:1].upper()}-{next_role[:1].upper()}"
            previous_handoff = {
                "from": role,
                "to": next_role,
                "summary": output[:500],
                "ref": handoff_id,
            }
            create_handoff(
                root,
                handoff_id,
                role,
                next_role,
                task_id,
                previous_handoff,
            )
            record_event(root, "handoff.created", session_id, {"handoff": handoff_id})
        update_session_status(root, session_id, "done")
        record_event(root, "session.completed", session_id, {"role": role})
        steps.append({"role": role, "status": "done", "output": output})
    return steps


def run_doctor(root: Path) -> dict[str, Any]:
    checks = []
    agent_dir = root / ".agent"
    checks.append(("agent_dir", agent_dir.exists(), "missing .agent" if not agent_dir.exists() else "ok"))

    def _parse(relative: str) -> bool:
        path = root / relative
        try:
            with path.open(encoding="utf-8") as handle:
                yaml.safe_load(handle)
            return True
        except Exception:
            return False

    manifest_ok = _parse(".agent/manifest.yaml")
    policies_ok = _parse(".agent/policies.yaml")
    checks.append(("manifest", manifest_ok, "unparsable" if not manifest_ok else "ok"))
    checks.append(("policies", policies_ok, "unparsable" if not policies_ok else "ok"))

    stale = []
    corrupt = []
    sessions_dir = root / ".agent/runtime/sessions"
    if sessions_dir.exists():
        for path in sorted(sessions_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                corrupt.append(path.name)
                continue
            if data.get("status") == "running":
                stale.append(data.get("id", path.stem))
    checks.append(
        ("sessions_parseable", not corrupt, f"corrupt: {corrupt}" if corrupt else "ok")
    )
    checks.append(("no_running_sessions", not stale, f"stale: {stale}" if stale else "ok"))

    ok = all(item[1] for item in checks)
    return {"ok": ok, "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}

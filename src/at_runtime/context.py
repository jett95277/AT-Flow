from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from at_runtime.policy import can_read
from at_runtime.registry import get_session
from at_runtime.workspace import load_policies


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_context(root: Path, session_id: str, explicit_refs: dict) -> dict[str, Any]:
    session = get_session(root, session_id)
    policies = load_policies(root)
    role = session["role"]
    filtered: list[str] = []
    task = yaml.safe_load(
        (root / ".agent/runtime/tasks" / f"{session['task_id']}.yaml").read_text(
            encoding="utf-8"
        )
    ) or {}

    handoff = explicit_refs.get("handoff", {"from": None, "summary": ""})
    handoff_resource = None
    if isinstance(handoff, dict):
        handoff_resource = handoff.get("resource")
        if handoff_resource is None and handoff.get("from") and handoff.get("to"):
            handoff_resource = f"handoff:{handoff['from']}_to_{handoff['to']}"
    if handoff_resource and not can_read(policies, role, handoff_resource):
        filtered.append(handoff_resource)
        handoff = {"from": None, "summary": ""}

    source_refs = list(explicit_refs.get("source", []))
    denied_source = [
        item for item in source_refs if not can_read(policies, role, "source")
    ]
    filtered.extend(denied_source)
    evidence = [
        {"file": item}
        for item in source_refs
        if can_read(policies, role, "source")
    ]

    memory_refs: list[str] = []
    for uri in explicit_refs.get("memory", []):
        try:
            resource = f"{uri.split('/')[2]}_memory"
        except IndexError:
            resource = None
        if resource and can_read(policies, role, resource):
            memory_refs.append(uri)
        else:
            filtered.append(uri)

    knowledge_refs: list[str] = []
    for ref in explicit_refs.get("wiki", []):
        if can_read(policies, role, "wiki"):
            knowledge_refs.append(ref)
        else:
            filtered.append(ref)

    return {
        "id": f"CB-{session['task_id']}-{session['role']}-001",
        "task": {"id": task.get("id"), "goal": task.get("goal")},
        "role": {"type": role},
        "constraints": list(explicit_refs.get("constraints", [])),
        "handoff": handoff,
        "evidence": evidence,
        "relevant_memory": memory_refs,
        "knowledge": knowledge_refs,
        "expected_output": list(explicit_refs.get("expected_output", [])),
        "token_budget": {"max_context": 32000},
        "policy": {"applied": True, "filtered": filtered},
        "provenance": {
            "session": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }

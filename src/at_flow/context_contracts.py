from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .providers import AgentContext


CONTEXT_SCHEMA_VERSION = 1


def build_agent_context_contract(context: "AgentContext") -> dict[str, Any]:
    permissions = _load_permissions(context.agent_permissions_path)
    read_permissions = permissions.get("read", {})
    write_permissions = permissions.get("write", {})
    can_access_project = bool(read_permissions.get("project") or write_permissions.get("project"))

    return {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "session_id": context.session.id,
        "task": context.session.task,
        "agent": context.agent,
        "step_index": context.step_index,
        "current_stage": context.session.current_stage,
        "permissions": {
            "read": read_permissions,
            "write": write_permissions,
        },
        "contracts": {
            "agent": str(context.agent_profile_path.resolve()),
            "permissions": str(context.agent_permissions_path.resolve()),
            "output": str(context.agent_output_path.resolve()),
        },
        "paths": {
            "agent": str(context.agent_dir.resolve()),
            "inbox": str(context.agent_inbox_dir.resolve()),
            "outbox": str(context.agent_outbox_dir.resolve()),
            "workspace": str(context.agent_workspace_dir.resolve()),
            "project": str(context.project_path.resolve()) if can_access_project else None,
            "shared": {
                "memory": None,
                "skills": None,
                "inbox": None,
            },
            "proposal_outbox": str((context.agent_outbox_dir / "proposals").resolve()),
            "memory_proposals": str((context.session_dir / "memory-proposals").resolve()),
        },
        "selected_files": {
            "shared_memory": _authorized_shared_files(context, read_permissions, "shared_memory", "memory"),
            "shared_skills": _authorized_shared_files(context, read_permissions, "shared_skills", "skills"),
            "shared_policies": _authorized_shared_files(context, read_permissions, "shared_policies", "policies"),
            "shared_docs": _authorized_shared_files(context, read_permissions, "shared_docs", "docs"),
            "shared_inbox": _authorized_shared_files(context, read_permissions, "shared_inbox", "inbox"),
        },
        "language": context.language or {},
        "input_paths": [str(item.resolve()) for item in context.inbox_files],
    }


def write_agent_context_contract(context: "AgentContext") -> Path:
    contract = build_agent_context_contract(context)
    context.agent_context_path.parent.mkdir(parents=True, exist_ok=True)
    context.agent_context_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    agent_copy = context.agent_dir / "context.json"
    agent_copy.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    return context.agent_context_path


def _load_permissions(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _authorized_shared_files(
    context: "AgentContext",
    read_permissions: dict[str, Any],
    permission_key: str,
    folder: str,
) -> list[str]:
    if not read_permissions.get(permission_key):
        return []
    root = context.shared_root / folder
    if not root.exists():
        return []
    return [str(path.resolve()) for path in sorted(root.iterdir()) if path.is_file()]

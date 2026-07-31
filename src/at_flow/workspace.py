from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_profiles import default_agent_output, default_agent_permissions, default_agent_profile
from .config import CONFIG_NAME, ConfigError, load_config, write_default_config
from .models import SessionState, now_iso
from .schema import validate_session_state


class WorkspaceError(RuntimeError):
    pass


class ATWorkspace:
    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self.root = root.resolve()
        self.config = config

    @classmethod
    def init(cls, root: Path) -> "ATWorkspace":
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        write_default_config(root)
        workspace = cls(root, load_config(root))
        workspace.ensure_layout()
        return workspace

    @classmethod
    def require(cls, root: Path) -> "ATWorkspace":
        root = root.resolve()
        if not (root / CONFIG_NAME).exists():
            raise ConfigError(f"Missing {CONFIG_NAME}. Run `python .\\at.py init` first.")
        workspace = cls(root, load_config(root))
        workspace.ensure_layout()
        return workspace

    def path_from_config(self, key: str) -> Path:
        raw = self.config["workspace"][key]
        path = Path(raw)
        if not path.is_absolute():
            path = self.root / path
        return path.resolve()

    @property
    def shared_root(self) -> Path:
        return self.path_from_config("shared_dir")

    @property
    def agents_root(self) -> Path:
        return self.path_from_config("agents_dir")

    @property
    def sessions_root(self) -> Path:
        return self.path_from_config("sessions_dir")

    @property
    def projects_root(self) -> Path:
        return self.path_from_config("projects_dir")

    def ensure_layout(self) -> None:
        for path in (
            self.shared_root,
            self.shared_root / "memory",
            self.shared_root / "skills",
            self.shared_root / "inbox",
            self.shared_root / "proposals",
            self.shared_root / "policies",
            self.shared_root / "docs",
            self.agents_root,
            self.sessions_root,
            self.projects_root,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self._ensure_shared_contract_files()
        for agent in self.config.get("pipeline", []):
            self.ensure_shared_agent_package(agent)

    def agent_profile_path(self, agent: str) -> Path:
        return self.agents_root / agent / "agent.md"

    def agent_permissions_path(self, agent: str) -> Path:
        return self.agents_root / agent / "permissions.json"

    def agent_output_path(self, agent: str) -> Path:
        return self.agents_root / agent / "output.md"

    def ensure_shared_agent_package(self, agent: str) -> None:
        package_dir = self.agents_root / agent
        package_dir.mkdir(parents=True, exist_ok=True)

        profile_path = self.agent_profile_path(agent)
        if not profile_path.exists():
            profile_path.write_text(default_agent_profile(agent).rstrip() + "\n", encoding="utf-8")

        permissions_path = self.agent_permissions_path(agent)
        if not permissions_path.exists():
            permissions = default_agent_permissions(agent)
            permissions["agent"] = agent
            permissions_path.write_text(json.dumps(permissions, indent=2) + "\n", encoding="utf-8")

        output_path = self.agent_output_path(agent)
        if not output_path.exists():
            output_path.write_text(default_agent_output(agent).rstrip() + "\n", encoding="utf-8")

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_root / session_id

    def state_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "state.json"

    def session_context_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "context"

    def session_context_path(self, session_id: str, agent: str) -> Path:
        return self.session_context_dir(session_id) / f"{agent}.json"

    def session_memory_proposals_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "memory-proposals"

    def create_session(self, session: SessionState) -> None:
        directory = self.session_dir(session.id)
        if directory.exists():
            raise WorkspaceError(f"Session already exists: {session.id}")
        (directory / "context").mkdir(parents=True, exist_ok=True)
        (directory / "memory-proposals").mkdir(parents=True, exist_ok=True)
        for agent in (step.agent for step in session.steps):
            self.prepare_agent_directories(session.id, agent)
            self.materialize_session_agent_package(session.id, agent)
        (directory / "handoff").mkdir(parents=True, exist_ok=True)
        (directory / "audit").mkdir(parents=True, exist_ok=True)
        self.save_session(session)

    def materialize_session_agent_profile(self, session_id: str, agent: str) -> Path:
        return self.materialize_session_agent_file(session_id, agent, "agent.md")

    def materialize_session_agent_permissions(self, session_id: str, agent: str) -> Path:
        return self.materialize_session_agent_file(session_id, agent, "permissions.json")

    def materialize_session_agent_output(self, session_id: str, agent: str) -> Path:
        return self.materialize_session_agent_file(session_id, agent, "output.md")

    def materialize_session_agent_package(self, session_id: str, agent: str) -> None:
        self.ensure_shared_agent_package(agent)
        self.materialize_session_agent_profile(session_id, agent)
        self.materialize_session_agent_permissions(session_id, agent)
        self.materialize_session_agent_output(session_id, agent)

    def materialize_session_agent_file(self, session_id: str, agent: str, filename: str) -> Path:
        source = self.agents_root / agent / filename
        target = self.session_agent_dir(session_id, agent) / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_shared_agent_package(agent)
        if not target.exists():
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return target

    def session_agent_dir(self, session_id: str, agent: str) -> Path:
        return self.session_dir(session_id) / "agents" / agent

    def session_agent_inbox_dir(self, session_id: str, agent: str) -> Path:
        return self.session_agent_dir(session_id, agent) / "inbox"

    def session_agent_outbox_dir(self, session_id: str, agent: str) -> Path:
        return self.session_agent_dir(session_id, agent) / "outbox"

    def session_agent_workspace_dir(self, session_id: str, agent: str) -> Path:
        return self.session_agent_dir(session_id, agent) / "workspace"

    def prepare_agent_directories(self, session_id: str, agent: str) -> None:
        for path in (
            self.session_context_dir(session_id),
            self.session_memory_proposals_dir(session_id),
            self.session_agent_dir(session_id, agent),
            self.session_agent_inbox_dir(session_id, agent),
            self.session_agent_outbox_dir(session_id, agent),
            self.session_agent_outbox_dir(session_id, agent) / "proposals",
            self.session_agent_outbox_dir(session_id, agent) / "logs",
            self.session_agent_workspace_dir(session_id, agent),
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _ensure_shared_contract_files(self) -> None:
        memory_defaults = {
            "user.md": "# User Memory\n\nLong-lived user preferences and constraints.\n",
            "project.md": "# Project Memory\n\nLong-lived project facts and conventions.\n",
            "decisions.md": "# Decisions\n\nAccepted durable decisions.\n",
            "rules.md": "# Rules\n\nDurable AT operating rules.\n",
        }
        for name, content in memory_defaults.items():
            path = self.shared_root / "memory" / name
            if not path.exists():
                path.write_text(content, encoding="utf-8")

        policy_defaults = {
            "context.md": "# Context Policy\n\nAgents may use only paths listed in their context contract.\n",
            "memory.md": "# Memory Policy\n\nAgents must request long-term memory changes through proposals.\n",
        }
        for name, content in policy_defaults.items():
            path = self.shared_root / "policies" / name
            if not path.exists():
                path.write_text(content, encoding="utf-8")

    def save_session(self, session: SessionState) -> None:
        session.updated_at = now_iso()
        directory = self.session_dir(session.id)
        directory.mkdir(parents=True, exist_ok=True)
        path = self.state_path(session.id)
        data = session.to_dict()
        validate_session_state(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def load_session(self, session_id: str) -> SessionState:
        path = self.state_path(session_id)
        if not path.exists():
            raise WorkspaceError(f"Unknown session: {session_id}")
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        session = SessionState.from_dict(data)
        validate_session_state(session.to_dict())
        return session

    def list_sessions(self) -> list[SessionState]:
        sessions: list[SessionState] = []
        if not self.sessions_root.exists():
            return sessions
        for state_path in sorted(self.sessions_root.glob("*/state.json")):
            with state_path.open("r", encoding="utf-8") as handle:
                sessions.append(SessionState.from_dict(json.load(handle)))
        return sessions

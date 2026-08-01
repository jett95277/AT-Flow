from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import subprocess
from typing import Any

from .models import ROLE_GOALS, SessionState


class ProviderError(RuntimeError):
    pass


@dataclass
class AgentContext:
    workspace_root: Path
    shared_root: Path
    session_dir: Path
    agent_dir: Path
    agent_inbox_dir: Path
    agent_outbox_dir: Path
    agent_workspace_dir: Path
    agent_profile_path: Path
    agent_permissions_path: Path
    agent_output_path: Path
    agent_context_path: Path
    project_path: Path
    session: SessionState
    step_index: int

    @property
    def agent(self) -> str:
        return self.session.steps[self.step_index].agent

    @property
    def prior_artifacts(self) -> list[tuple[str, str]]:
        return self.session.prior_artifacts(self.step_index)

    @property
    def inbox_files(self) -> list[Path]:
        if not self.agent_inbox_dir.exists():
            return []
        return sorted(path for path in self.agent_inbox_dir.iterdir() if path.is_file())


@dataclass
class AgentResult:
    content: str


class Provider:
    def run(self, context: AgentContext, prompt: str) -> AgentResult:
        raise NotImplementedError


class MockProvider(Provider):
    def run(self, context: AgentContext, prompt: str) -> AgentResult:
        inbox = "\n".join(f"- {path.name}: {path}" for path in context.inbox_files)
        if not inbox:
            inbox = "- none"
        return AgentResult(content=_mock_artifact(context, inbox))


class ProcessProvider(Provider):
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config

    def run(self, context: AgentContext, prompt: str) -> AgentResult:
        command = self._command()
        prompt_mode = self.config.get("prompt_mode", "stdin")
        cwd = self._cwd(context)
        timeout = int(self.config.get("timeout_seconds", 1800))

        stdin: str | None = None
        if prompt_mode == "stdin":
            stdin = prompt
            args = command
        elif prompt_mode == "arg":
            args = [*command, prompt]
        elif prompt_mode == "file":
            prompt_path = context.agent_dir / "prompt.md"
            prompt_path.write_text(prompt, encoding="utf-8")
            args = [*command, str(prompt_path)]
        else:
            raise ProviderError(f"Unsupported prompt_mode for {self.name}: {prompt_mode}")

        env = self._base_env()
        env.update(
            {
                "AT_SESSION_ID": context.session.id,
                "AT_AGENT": context.agent,
                "AT_AGENT_DIR": str(context.agent_dir),
                "AT_INBOX": str(context.agent_inbox_dir),
                "AT_OUTBOX": str(context.agent_outbox_dir),
                "AT_AGENT_WORKSPACE": str(context.agent_workspace_dir),
                "AT_PERMISSIONS": str(context.agent_permissions_path),
                "AT_OUTPUT_CONTRACT": str(context.agent_output_path),
                "AT_CONTEXT": str(context.agent_context_path),
                "AT_PROJECT_PATH": _env_project_path(context),
                "AT_SHARED_MEMORY": "",
                "AT_SHARED_SKILLS": "",
                "AT_SHARED_INBOX": "",
            }
        )
        env.update({str(key): str(value) for key, value in self.config.get("env", {}).items()})

        try:
            completed = subprocess.run(
                args,
                input=stdin,
                text=True,
                capture_output=True,
                cwd=str(cwd),
                env=env,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ProviderError(f"Provider command not found for {self.name}: {command[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(f"Provider {self.name} timed out after {timeout}s") from exc

        output = completed.stdout.strip()
        stderr = completed.stderr.strip()
        if completed.returncode != 0:
            detail = stderr or output or f"exit code {completed.returncode}"
            raise ProviderError(f"Provider {self.name} failed: {detail}")
        if stderr:
            output = f"{output}\n\n[stderr]\n{stderr}" if output else f"[stderr]\n{stderr}"
        return AgentResult(content=output or "(provider returned no output)")

    def _command(self) -> list[str]:
        raw = self.config.get("command")
        if not raw:
            raise ProviderError(f"Provider {self.name} has no command configured")
        if isinstance(raw, str):
            return shlex.split(raw)
        return [str(item) for item in raw]

    def _base_env(self) -> dict[str, str]:
        policy = self.config.get("env_policy", "minimal")
        if policy == "inherit":
            return os.environ.copy()
        if policy != "minimal":
            raise ProviderError(f"Unsupported env_policy for {self.name}: {policy}")
        passthrough = self.config.get("env_passthrough", _DEFAULT_ENV_PASSTHROUGH)
        return {
            key: os.environ[key]
            for key in passthrough
            if key in os.environ
        }

    def _cwd(self, context: AgentContext) -> Path:
        mode = self.config.get("cwd", "workspace")
        if mode == "workspace":
            return context.agent_workspace_dir
        if mode == "root":
            return context.workspace_root
        if mode == "project":
            return context.project_path
        if mode == "session":
            return context.session_dir
        if mode == "agent":
            return context.agent_dir
        return Path(mode).resolve()


def build_prompt(context: AgentContext) -> str:
    agent = context.agent
    agent_profile = _read_agent_profile(context)
    permissions = _read_text(context.agent_permissions_path)
    output_contract = _read_text(context.agent_output_path)
    context_contract = _read_text(context.agent_context_path)
    inbox = "\n".join(f"- {path.name}: {path}" for path in context.inbox_files)
    if not inbox:
        inbox = "- none"
    return f"""You are the AT `{agent}` agent.

Agent Contract (`agent.md`):
{agent_profile}

Agent Permissions (`permissions.json`):
{permissions}

Output Contract (`output.md`):
{output_contract}

Context Contract (`context.json`):
{context_contract}

Task:
{context.session.task}

Boundaries:
- Follow the agent contract above as the primary role and boundary definition.
- Use only paths explicitly listed in the context contract.
- Treat files in your inbox as handoff input.
- Do not read or write another agent's directory.
- Write the stable result to `outbox/artifact.md`.
- Put shared memory, skill, or policy update requests under `outbox/proposals/`.

Inbox files:
{inbox}
"""


_MOCK_SECTIONS: dict[str, list[str]] = {
    "main": [
        "Task Summary",
        "Goal",
        "Non-Goals",
        "Constraints",
        "Acceptance Criteria",
        "Risks And Questions",
        "Handoff To Analysis",
    ],
    "analysis": [
        "Relevant Project Facts",
        "Proposed Approach",
        "Files Or Areas To Inspect Or Change",
        "Implementation Steps For Code",
        "Verification Plan For Test",
        "Risks And Open Questions",
    ],
    "code": [
        "Changed Files",
        "Behavioral Changes",
        "Assumptions",
        "Commands Run",
        "Risks Left For Test",
        "Verification Suggestions",
    ],
    "test": [
        "Checks Performed",
        "Result",
        "Command Output Summary",
        "Defects Found",
        "Skipped Checks",
        "Residual Risk",
        "Recommended Next State",
    ],
}


def _mock_artifact(context: AgentContext, inbox: str) -> str:
    sections = _MOCK_SECTIONS.get(context.agent, ["Summary"])
    lines = [
        f"# {context.agent} artifact",
        "",
        f"Session: {context.session.id}",
        f"Task: {context.session.task}",
        f"Role: {ROLE_GOALS.get(context.agent, context.agent)}",
        f"Context contract: {context.agent_context_path}",
        "",
    ]
    for section in sections:
        lines.extend(
            [
                f"## {section}",
                "",
                f"Mock {context.agent} output for `{section}`.",
                "",
            ]
        )
    lines.extend(["## Inputs", "", f"Inbox: {context.agent_inbox_dir}", "", "Inbox files:", inbox, ""])
    return "\n".join(lines)


_DEFAULT_ENV_PASSTHROUGH = [
    "PATH",
    "PATHEXT",
    "SystemRoot",
    "ComSpec",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "LANG",
]


def _read_agent_profile(context: AgentContext) -> str:
    if context.agent_profile_path.exists():
        return context.agent_profile_path.read_text(encoding="utf-8").strip()
    return ROLE_GOALS.get(context.agent, context.agent)


def _read_text(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return "(missing)"


def _read_permissions(context: AgentContext) -> dict[str, Any]:
    if not context.agent_permissions_path.exists():
        return {}
    with context.agent_permissions_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _can_access_project(context: AgentContext) -> bool:
    permissions = _read_permissions(context)
    read = permissions.get("read", {})
    write = permissions.get("write", {})
    return bool(read.get("project") or write.get("project"))


def _can_read_shared(context: AgentContext, permission_key: str) -> bool:
    permissions = _read_permissions(context)
    read = permissions.get("read", {})
    return bool(read.get(permission_key))


def _project_access_label(context: AgentContext) -> str:
    if _can_access_project(context):
        return str(context.project_path)
    return "(not granted to this agent)"


def _env_project_path(context: AgentContext) -> str:
    if _can_access_project(context):
        return str(context.project_path)
    return ""


def make_provider(name: str, config: dict[str, Any]) -> Provider:
    provider_config = config.get("providers", {}).get(name)
    if provider_config is None:
        raise ProviderError(f"Unknown provider: {name}")
    provider_type = provider_config.get("type", name)
    if provider_type == "mock":
        return MockProvider()
    if provider_type == "process":
        return ProcessProvider(name, provider_config)
    raise ProviderError(f"Unsupported provider type for {name}: {provider_type}")


def resolve_agent_provider(config: dict[str, Any], session_provider: str, agent: str) -> str:
    routes = config.get("agent_providers", {})
    if isinstance(routes, dict):
        route = routes.get(agent)
        if isinstance(route, str) and route.strip():
            return route
    return session_provider

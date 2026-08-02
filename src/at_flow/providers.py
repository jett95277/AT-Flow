from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import shutil
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
    language: dict[str, Any] | None = None

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
        cwd = self._cwd(context)
        output = run_process_prompt(
            self.name,
            self.config,
            prompt,
            cwd=cwd,
            env_overrides={
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
            },
            prompt_path=context.agent_dir / "prompt.md",
        )
        return AgentResult(content=output or "(provider returned no output)")

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


def run_process_prompt(
    name: str,
    provider_config: dict[str, Any],
    prompt: str,
    *,
    cwd: Path,
    env_overrides: dict[str, str] | None = None,
    prompt_path: Path | None = None,
    stderr_path: Path | None = None,
) -> str:
    command = _provider_command(provider_config, name)
    prompt_mode = provider_config.get("prompt_mode", "stdin")
    timeout = int(provider_config.get("timeout_seconds", 1800))
    encoding = str(provider_config.get("encoding", "utf-8"))

    stdin: bytes | None = None
    if prompt_mode == "stdin":
        try:
            stdin = prompt.encode(encoding)
        except (LookupError, UnicodeEncodeError) as exc:
            raise ProviderError(f"Provider {name} prompt is not valid {encoding}: {exc}") from exc
        args = command
    elif prompt_mode == "arg":
        args = [*command, prompt]
    elif prompt_mode == "file":
        file_path = prompt_path or cwd / "prompt.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(prompt, encoding="utf-8")
        args = [*command, str(file_path)]
    else:
        raise ProviderError(f"Unsupported prompt_mode for {name}: {prompt_mode}")

    cwd.mkdir(parents=True, exist_ok=True)
    env = _process_base_env(name, provider_config)
    env.update({str(key): str(value) for key, value in provider_config.get("env", {}).items()})
    env.update(env_overrides or {})
    process_args = _platform_process_args(args)
    try:
        completed = _run_managed_process(
            process_args,
            stdin=stdin,
            cwd=str(cwd),
            env=env,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ProviderError(f"Provider command not found for {name}: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProviderError(f"Provider {name} timed out after {timeout}s") from exc
    except OSError as exc:
        raise ProviderError(f"Provider {name} could not start: {exc}") from exc

    output = _decode_process_stream(name, "stdout", completed.stdout, encoding).strip()
    stderr = _decode_process_stream(name, "stderr", completed.stderr, encoding).strip()
    if completed.returncode != 0:
        if stderr and stderr_path is not None:
            _write_process_stderr(stderr_path, stderr)
            detail = f"exit code {completed.returncode}; stderr logged separately"
        else:
            detail = stderr or output or f"exit code {completed.returncode}"
        raise ProviderError(f"Provider {name} failed: {detail}")
    if stderr:
        if stderr_path is not None:
            _write_process_stderr(stderr_path, stderr)
        else:
            output = f"{output}\n\n[stderr]\n{stderr}" if output else f"[stderr]\n{stderr}"
    return output


def _provider_command(provider_config: dict[str, Any], name: str) -> list[str]:
    raw = provider_config.get("command")
    if not raw:
        raise ProviderError(f"Provider {name} has no command configured")
    if isinstance(raw, str):
        return shlex.split(raw)
    return [str(item) for item in raw]


def _platform_process_args(command: list[str]) -> list[str]:
    if os.name != "nt":
        return command
    resolved = shutil.which(command[0])
    if not resolved or Path(resolved).suffix.lower() not in {".cmd", ".bat"}:
        return command
    comspec = os.environ.get("ComSpec") or os.environ.get("COMSPEC") or "cmd.exe"
    script_command = subprocess.list2cmdline([resolved, *command[1:]])
    return [comspec, "/d", "/s", "/c", script_command]


def _run_managed_process(
    args: list[str],
    *,
    stdin: bytes | None,
    cwd: str,
    env: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[bytes]:
    options: dict[str, Any] = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    process = subprocess.Popen(
        args,
        stdin=subprocess.PIPE if stdin is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
        **options,
    )
    try:
        stdout, stderr = process.communicate(input=stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
        raise
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT)
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            pass
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


def _decode_process_stream(name: str, stream: str, value: bytes | str | None, encoding: str) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return value.decode(encoding)
    except (LookupError, UnicodeDecodeError) as exc:
        raise ProviderError(
            f"Provider {name} {stream} is not valid {encoding}: {exc}"
        ) from exc


def _write_process_stderr(path: Path, stderr: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stderr + "\n", encoding="utf-8")


def _process_base_env(name: str, provider_config: dict[str, Any]) -> dict[str, str]:
    policy = provider_config.get("env_policy", "minimal")
    if policy == "inherit":
        return os.environ.copy()
    if policy != "minimal":
        raise ProviderError(f"Unsupported env_policy for {name}: {policy}")
    passthrough = provider_config.get("env_passthrough", _DEFAULT_ENV_PASSTHROUGH)
    return {key: os.environ[key] for key in passthrough if key in os.environ}


def build_prompt(context: AgentContext) -> str:
    agent = context.agent
    agent_profile = _read_agent_profile(context)
    permissions = _read_text(context.agent_permissions_path)
    output_contract = _read_text(context.agent_output_path)
    context_contract = _read_text(context.agent_context_path)
    inbox = "\n".join(f"- {path.name}: {path}" for path in context.inbox_files)
    if not inbox:
        inbox = "- none"
    original_task = _original_task_section(context)
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
{_task_for_prompt(context)}
{original_task}

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


def _task_for_prompt(context: AgentContext) -> str:
    language = context.language or {}
    task_runtime = language.get("task_runtime")
    if isinstance(task_runtime, str) and task_runtime.strip():
        return task_runtime.strip()
    return context.session.task


def _original_task_section(context: AgentContext) -> str:
    language = context.language or {}
    input_translation = language.get("input_translation", {})
    if isinstance(input_translation, dict) and input_translation.get("status") == "completed":
        return ""
    return f"\nOriginal User Task:\n{context.session.task}\n"


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
        f"Task: {_task_for_prompt(context)}",
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


def check_provider_capability(name: str, config: dict[str, Any]) -> dict[str, Any]:
    provider_config = config.get("providers", {}).get(name)
    if provider_config is None:
        return {
            "name": name,
            "available": False,
            "provider_type": "unknown",
            "detail": f"unknown provider: {name}",
        }

    provider_type = provider_config.get("type", name)
    if provider_type == "mock":
        return {
            "name": name,
            "available": True,
            "provider_type": "mock",
            "detail": "mock provider is always available",
        }

    if provider_type == "process":
        command = _provider_command_for_check(provider_config)
        if not command:
            return {
                "name": name,
                "available": False,
                "provider_type": "process",
                "detail": "provider command is not configured",
            }
        executable = command[0]
        path = shutil.which(executable)
        if path:
            return {
                "name": name,
                "available": True,
                "provider_type": "process",
                "detail": f"command found: {path}",
            }
        return {
            "name": name,
            "available": False,
            "provider_type": "process",
            "detail": f"command not found: {executable}",
        }

    return {
        "name": name,
        "available": False,
        "provider_type": str(provider_type),
        "detail": f"unsupported provider type: {provider_type}",
    }


def _provider_command_for_check(provider_config: dict[str, Any]) -> list[str]:
    raw = provider_config.get("command")
    if not raw:
        return []
    if isinstance(raw, str):
        return shlex.split(raw)
    return [str(item) for item in raw]


def resolve_agent_provider(config: dict[str, Any], session_provider: str, agent: str) -> str:
    if session_provider != "auto":
        return session_provider

    routes = config.get("agent_providers", {})
    if isinstance(routes, dict):
        route = routes.get(agent)
        if isinstance(route, str) and route.strip():
            return route

    default_provider = config.get("default_provider", "mock")
    if isinstance(default_provider, str) and default_provider.strip():
        return default_provider
    return "mock"

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from typing import Any


class ExecutionAdapter:
    def spawn(self, bundle: dict, role: str, cwd: Path) -> str:
        raise NotImplementedError


class LocalAdapter(ExecutionAdapter):
    def __init__(self, command: list[str] | None = None) -> None:
        self.command = command or [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--ephemeral",
            "--color",
            "never",
            "-",
        ]

    def spawn_command(self) -> list[str]:
        return list(self.command)

    def spawn(self, bundle: dict[str, Any], role: str, cwd: Path) -> str:
        prompt = build_prompt(bundle, role)
        command = _platform_command(self.command)
        completed = subprocess.run(
            command,
            input=prompt.encode("utf-8"),
            cwd=str(cwd),
            capture_output=True,
            timeout=1800,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"agent execution failed ({completed.returncode}): "
                f"{completed.stderr.decode('utf-8', errors='replace')[-500:]}"
            )
        return completed.stdout.decode("utf-8", errors="replace")


def _platform_command(command: list[str]) -> list[str]:
    """Wrap .cmd/.bat shims through cmd.exe on Windows (e.g. fnm codex.CMD)."""
    if os.name != "nt":
        return command
    resolved = shutil.which(command[0])
    if not resolved or Path(resolved).suffix.lower() not in {".cmd", ".bat"}:
        return command
    comspec = os.environ.get("ComSpec") or os.environ.get("COMSPEC") or "cmd.exe"
    script_command = subprocess.list2cmdline([resolved, *command[1:]])
    return [comspec, "/d", "/s", "/c", script_command]


def build_prompt(bundle: dict[str, Any], role: str) -> str:
    task = bundle.get("task", {})
    handoff = bundle.get("handoff", {})
    constraints = bundle.get("constraints", [])
    memory = bundle.get("relevant_memory", [])
    knowledge = bundle.get("knowledge", [])
    return f"""You are the AT `{role}` agent for task {task.get('id')}.

Goal: {task.get('goal')}

Constraints:
{chr(10).join('- ' + item for item in constraints) or '- none'}

Handoff from {handoff.get('from')}:
{handoff.get('summary')}

Relevant memory refs:
{chr(10).join(memory) or '- none'}

Knowledge refs:
{chr(10).join(knowledge) or '- none'}

Produce the expected output and nothing else.
"""

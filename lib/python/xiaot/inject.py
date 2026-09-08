"""Agent injection generator (M5b).

Writes orchestration command files + a driver skill into a project's
`.opencode/` so an agent (opencode) discovers xiaot's orchestration
commands at startup and calls them during a session (aligned with how the
spec tool injects its opsx commands/skills).

Command bodies invoke the `xiaot` CLI (assumed installed on PATH or via
`python -m xiaot`). Injection is project-level; startup discovery is the
agent's own mechanism.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

CORE_COMMANDS = ["task", "retrieve", "plan", "settle", "checkpoint", "rollback"]

# Short usage guidance per command (body of each .opencode/commands file).
_USAGE: dict[str, str] = {
    "task": ("Start/resume the orchestration loop for a user task. Call "
             "`xiaot task \"<task>\" [--project X] [--resume <id>]`. Returns JSON: "
             "task_id, workspace, memory (injected summary), context fragment. "
             "Execute the context.instruction, then settle when done."),
    "retrieve": ("Inject task-relevant memory: `xiaot retrieve \"<task>\" "
                 "[--project X]`. Use mid-task when more project context is needed."),
    "plan": ("Produce + persist a plan document: `xiaot plan \"<task>\"`. "
             "Writes plan.md into the task workspace."),
    "settle": ("End-of-task memory settling: `xiaot settle <task_id> "
               "[--status success] [--output ...] [--text <candidate>]...`. "
               "Returns comparison suggestions; promotions are MANUAL."),
    "checkpoint": ("Snapshot task workspace + memory at a key node: "
                   "`xiaot checkpoint <task_id> [--label X]`."),
    "rollback": ("Restore task workspace from a timeline node: "
                 "`xiaot rollback <node_id>`."),
}

_SKILL_BODY = """# xiaot task orchestration driver (mandatory for development tasks)

## Trigger rule (strong)

Use THIS skill whenever the user gives a DEVELOPMENT task: implement /
refactor / fix / add feature / continue developing / build X / write code /
modify a module. Do NOT treat such a task as a plain conversation or route
it to memory-restore skills (xiaot-continue) - route it through the xiaot
task orchestration loop below.

## Iron rule: plan-then-inject (hard boundary)

Do NOT start editing code before you have run `xiaot task` and received its
context fragment. "带记忆开工、留记忆收工" is the loop:

1. **Start**: run
   `xiaot task "<task>" [--project X] [--resume <task_id>]`
   Returns JSON: task_id, workspace, memory (injected summaries), context
   fragment (instruction + memory_summary + refs). Empty memory on a fresh
   project is fine - proceed.
   Project name discipline: use ONE canonical `--project` value for the whole
   project (default = the directory name reported by `xiaot init`). Never
   invent variants - memory injection keys on the project name across
   sessions, so a drifted name makes memory invisible.
2. **Execute**: follow `context.instruction`; use relevant memory_summary
   items. Need more context mid-task? Call `xiaot retrieve "<need>" --project X`.
   Large task flagged by `spec.needs_spec`? Its `spec.guidance` says whether to
   run the spec workflow first; the flag is advice, never a blocker - proceed
   on the base path if the spec workflow is overkill for this task.
3. **Milestones**: `xiaot checkpoint <task_id> --label X` at key nodes.
4. **Finish**: after completing call
   `xiaot settle <task_id> --status success --output "<summary>" [--text "<candidate>"]...`
   settle returns duplicate/review suggestions with scope hints - present
   them. Promotions are MANUAL; never auto-write memory.
5. On failure: `xiaot settle ... --status failed`; only confirmed facts /
   unresolved become candidates, never the failure itself.

## Memory helpers are NOT substitutes

xiaot-memo / xiaot-continue / xiaot-topic / xiaot-memory-manage stay
available for record / restore / tidy actions, but they do NOT start task
orchestration. A development task ALWAYS goes through `xiaot task` first.

Commands return machine-readable JSON; never dump internal stores.
The `xiaot` CLI must be on PATH (or `python -m xiaot` with PYTHONPATH).
"""


def _command_md(name: str) -> str:
    return (f"---\ndescription: xiaot orchestration - {name}. "
            f"Use when the task matches this orchestration step.\n---\n\n"
            f"{_USAGE[name]}\n")


def _skill_md() -> str:
    return ("---\nname: xiaot-orchestrate\n"
            "description: MANDATORY orchestration entry for development tasks "
            "(implement/refactor/fix/add feature/continue developing). Use when "
            "the user gives any coding/development task - run `xiaot task` first "
            "to get injected memory + context fragment, execute, then `xiaot "
            "settle` to leave memory. Never start a dev task as plain chat or via "
            "memory-restore skills.\n"
            "allowed-tools: Bash(xiaot:*)\n"
            "compatibility: Requires xiaot CLI.\n---\n\n" + _SKILL_BODY)


def generate(root: Path, agent: str = "opencode") -> dict[str, Any]:
    """Write orchestration commands + driver skill into <root>/.<agent>/."""
    base = root / f".{agent}"
    cmds = base / "commands"
    skills = base / "skills" / "xiaot-orchestrate"
    cmds.mkdir(parents=True, exist_ok=True)
    skills.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for name in CORE_COMMANDS:
        (cmds / f"xiaot-{name}.md").write_text(_command_md(name), encoding="utf-8")
        written.append(f".{agent}/commands/xiaot-{name}.md")
    (skills / "SKILL.md").write_text(_skill_md(), encoding="utf-8")
    written.append(f".{agent}/skills/xiaot-orchestrate/SKILL.md")
    return {"ok": True, "agent": agent, "files": written,
            "note": "startup discovery is the agent's mechanism; verify in a "
                    "live opencode session"}

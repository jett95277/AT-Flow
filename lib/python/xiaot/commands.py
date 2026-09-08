"""Core orchestration commands (M2): task / retrieve / plan / context / settle.

Each command returns machine-readable JSON for the calling agent. Execution is
performed by the calling agent; xiaot produces guidance + snapshots. Memory is
A-model (medium/long only; short process excluded); settling compares
candidates and requires human confirmation for any promotion.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from xiaot import workspace
from xiaot.models import ContextPack, Task


def _resolve_root() -> Path:
    """Resolve project root: env XIAOT_PROJECT > cwd (upward for a real
    project marker). A project marker is `.agent` (memory store) or a `.xiaot`
    that actually holds workspace/. The user HOME dir is never a project root
    (its .agent/.xiaot are deployment/history, not a project)."""
    env = os.environ.get("XIAOT_PROJECT")
    if env:
        return Path(env)
    home = str(Path.home()).lower()
    p = Path.cwd()
    while p:
        if str(p).lower() == home:
            break  # home is not a project root
        if (p / ".agent").exists():
            return p
        proj_xiaot = p / ".xiaot"
        if proj_xiaot.exists() and (proj_xiaot / "workspace").exists():
            return p
        parent = p.parent
        if parent == p:
            break
        p = parent
    return Path.cwd()


# ---- init: initialize a project for xiaot orchestration ------------------
def init(project_root: str | Path | None = None,
         agent: str = "opencode",
         project_name: str | None = None) -> dict[str, Any]:
    """One-command project init: create .xiaot workspace + inject agent dir.

    Usage: xiaot init --dir <project> [--project <canonical-name>]
    Pins the canonical project name (.xiaot/project.json): memory injection
    keys on it across sessions. Default name = project directory name.
    """
    root = Path(project_root) if project_root else _resolve_root()
    root = root.resolve()
    if not root.exists():
        return {"ok": False, "error": f"project dir not found: {root}"}
    # 1) .xiaot/workspace + canonical project name
    ws = workspace.xiaot_root(root)
    (ws / "workspace").mkdir(parents=True, exist_ok=True)
    name = project_name or root.name
    workspace.write_project_name(root, name)
    # 2) inject orchestration commands/skill
    from xiaot import inject
    inj = inject.generate(root, agent=agent)
    return {"ok": True, "project": str(root), "project_name": name,
            "workspace_dir": str(ws / "workspace"),
            "inject": inj,
            "note": (f"canonical project name: {name}; keep --project the same "
                     "across sessions so memory injects back. Remember to "
                     "gitignore .xiaot/ and .opencode/ (or commit the injected "
                     "files)")}


# ---- confirm: human-approved promotion into medium memory (settle close) --
def confirm(text: str, scope: str = "task", project: str | None = None,
            task_id: str | None = None, evidence: str | None = None,
            root: Path | None = None) -> dict[str, Any]:
    """Thin command over Orchestrator.confirm (v3.1 layering).

    After the human approves a settle suggestion, write it into medium.
    A-model: promotions are manual - this command is the manual gate.
    """
    from xiaot.orchestrator import assemble_default

    orch = assemble_default(root=root or _resolve_root())
    return orch.confirm(text, scope=scope, project=project, task_id=task_id,
                        evidence=evidence)


# ---- task: start or resume the closed loop ---------------------------------
def task(prompt: str, project: str | None = None, session: str | None = None,
         resume: str | None = None, budget: int = 5,
         root: Path | None = None) -> dict[str, Any]:
    """Thin command: assemble the Orchestrator (default wiring) and run it.

    v3.1 layering: all orchestration logic lives in Orchestrator.run_task;
    this command only resolves root + assembles ports + returns the JSON.
    """
    from xiaot.orchestrator import assemble_default

    orch = assemble_default(root=root or _resolve_root())
    return orch.run_task(prompt, project=project, session=session,
                         resume=resume, budget=budget)


# ---- retrieve: inject A-model task-relevant memory ------------------------
def retrieve(prompt: str, project: str | None = None, session: str | None = None,
             budget: int = 5, root: Path | None = None) -> dict[str, Any]:
    """Thin command over Orchestrator.retrieve (v3.1 layering)."""
    from xiaot.orchestrator import assemble_default

    orch = assemble_default(root=root or _resolve_root())
    return orch.retrieve(prompt, project=project, session=session,
                         budget=budget)


# ---- plan: produce and persist the plan document --------------------------
def plan(prompt: str, goal: str | None = None, steps: list[str] | None = None,
         acceptance: str | None = None, project: str | None = None,
         root: Path | None = None) -> dict[str, Any]:
    """Thin command over Orchestrator.plan (v3.1 layering)."""
    from xiaot.orchestrator import assemble_default

    orch = assemble_default(root=root or _resolve_root())
    return orch.plan(prompt, goal=goal, steps=steps, acceptance=acceptance,
                     project=project)


# ---- context: assemble guidance fragment (instruction + summary + refs) ---
def build_context(t: Task, memory: dict[str, Any],
                  skill_hints: list[dict[str, Any]] | None = None,
                  spec_decision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble context fragment; memory inline summary bounded by budget.

    spec_path / workspace_ref are optional pointer slots: filled by whoever
    drives a spec work unit or needs to reference on-disk artifacts; None when
    the plain path is used (light task -> workspace dir only).
    """
    ctx = ContextPack(task=t)
    refs = memory.get("refs", {}) if memory else {}
    spec_dec = spec_decision or {"needs_spec": False}
    return {
        "task_id": t.id,
        "instruction": f"Execute: {t.prompt}",
        "memory_present": bool(memory.get("present")),
        "memory_summary": memory.get("summary", []) if memory else [],
        "memory_refs": refs,          # over-budget read-by-reference info
        "skill_hints": skill_hints or [],
        "spec_decision": spec_dec,
        "spec_path": spec_dec.get("spec_path"),
        "workspace_ref": spec_dec.get("workspace_ref"),
        "constraints": ctx.constraints,
    }


# ---- settle: end-of-task comparison suggestions (human confirms all) ------
def settle(task_id: str, status: str = "success", output: str = "",
           candidates: list[dict[str, Any]] | None = None,
           root: Path | None = None) -> dict[str, Any]:
    """Thin command over Orchestrator.settle (v3.1 layering)."""
    from xiaot.orchestrator import assemble_default

    orch = assemble_default(root=root or _resolve_root())
    return orch.settle(task_id, status=status, output=output,
                       candidates=candidates)

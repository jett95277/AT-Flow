"""Core orchestration commands (M2): task / retrieve / plan / context / settle.

Each command returns machine-readable JSON for the calling agent. Execution is
performed by the calling agent; xiaot produces guidance + snapshots. Memory is
A-model (medium/long only; short process excluded); settling compares
candidates and requires human confirmation for any promotion.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from xiaot import memory_service, skill_router, spec_adapter, spec_router, workspace
from xiaot.models import ContextPack, Task


def _new_task_id() -> str:
    return f"task-{uuid.uuid4().hex[:8]}"


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


# ---- task: start or resume the closed loop ---------------------------------
def task(prompt: str, project: str | None = None, session: str | None = None,
         resume: str | None = None, budget: int = 5,
         root: Path | None = None) -> dict[str, Any]:
    root = root or _resolve_root()
    if resume:
        if not workspace.workspace_exists(root, resume):
            return {"ok": False, "error": f"workspace for {resume} not found"}
        task_id = resume
        state = workspace.read_workspace(root, task_id)
        prompt = state.get("plan", {}).get("goal", prompt) or prompt
    else:
        task_id = _new_task_id()
        plan = {"title": project or task_id, "goal": prompt,
                "steps": ["analyze and execute per agent"], "acceptance": "user confirms"}
        workspace.write_plan(root, task_id, plan)
        workspace.write_result(root, task_id, "planning", prompt)
        state = {"task_id": task_id, "plan": plan}

    task_obj = {"id": task_id, "project": project, "session_id": session}
    memory = memory_service.retrieve(root, task_obj, budget=budget)
    # skill routing + spec decision feed the guidance fragment
    skill_hints = skill_router.resolve(prompt)
    spec_dec = spec_router.should_spec(prompt)
    if spec_dec.get("needs_spec") and not spec_adapter.available():
        return {"ok": False, "error":
                "task needs the spec workflow but the spec CLI is unavailable "
                "(no silent fallback to plain execution)"}
    ctx = build_context(Task(id=task_id, prompt=prompt, project=project,
                             session_id=session), memory,
                        skill_hints=skill_hints, spec_decision=spec_dec)
    workspace.write_context_snapshot(root, task_id, ctx)
    return {"ok": True, "command": "task", "task_id": task_id,
            "workspace": str(workspace.workspace_dir(root, task_id)),
            "memory": memory, "skills": skill_hints, "spec": spec_dec,
            "context": ctx, "state": state}


# ---- retrieve: inject A-model task-relevant memory ------------------------
def retrieve(prompt: str, project: str | None = None, session: str | None = None,
             budget: int = 5, root: Path | None = None) -> dict[str, Any]:
    root = root or _resolve_root()
    task = {"id": _new_task_id(), "project": project, "session_id": session}
    return {"command": "retrieve", "prompt": prompt,
            **memory_service.retrieve(root, task, budget=budget)}


# ---- plan: produce and persist the plan document --------------------------
def plan(prompt: str, goal: str | None = None, steps: list[str] | None = None,
         acceptance: str | None = None, project: str | None = None,
         root: Path | None = None) -> dict[str, Any]:
    root = root or _resolve_root()
    task_id = _new_task_id()
    plan_doc = {
        "title": project or task_id,
        "goal": goal or prompt,
        "steps": steps or ["analyze and execute per agent"],
        "acceptance": acceptance or "user confirms",
    }
    workspace.write_plan(root, task_id, plan_doc)
    return {"command": "plan", "task_id": task_id,
            "plan_path": str(workspace.workspace_dir(root, task_id) / "plan.md"),
            "plan": plan_doc}


# ---- context: assemble guidance fragment (instruction + summary + refs) ---
def build_context(t: Task, memory: dict[str, Any],
                  skill_hints: list[dict[str, Any]] | None = None,
                  spec_decision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble context fragment; memory inline summary bounded by budget."""
    ctx = ContextPack(task=t)
    refs = memory.get("refs", {}) if memory else {}
    return {
        "task_id": t.id,
        "instruction": f"Execute: {t.prompt}",
        "memory_present": bool(memory.get("present")),
        "memory_summary": memory.get("summary", []) if memory else [],
        "memory_refs": refs,          # over-budget read-by-reference info
        "skill_hints": skill_hints or [],
        "spec_decision": spec_decision or {"needs_spec": False},
        "spec_path": None,
        "workspace_ref": None,
        "constraints": ctx.constraints,
    }


# ---- settle: end-of-task comparison suggestions (human confirms all) ------
def settle(task_id: str, status: str = "success", output: str = "",
           candidates: list[dict[str, Any]] | None = None,
           root: Path | None = None) -> dict[str, Any]:
    root = root or _resolve_root()
    workspace.write_result(root, task_id, status, output)
    suggestions = memory_service.suggest_settle(root, task_id, candidates)
    return {"command": "settle", "task_id": task_id, "status": status,
            **suggestions}


COMMANDS = {"task": task, "retrieve": retrieve, "plan": plan,
            "context": build_context, "settle": settle}

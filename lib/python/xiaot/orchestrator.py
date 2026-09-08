"""Orchestration core (v3.1 layering).

Orchestrator owns the task lifecycle (state machine) and coordinates the
three peer capabilities (memory / skill / spec) through injected ports. The
core's business methods only ever touch port objects (`self._memory`,
`self._skills`, ...) — never concrete adapters. Default assembly with the
current implementations is provided by `assemble_default` so existing command
behaviour and JSON contract stay unchanged.

Lifecycle (derived from workspace artifacts, spec orchestration/task-lifecycle):
planning -> ready -> (agent executes in-session) -> completed/failed.
Phase is never kept as a redundant record; `phase_of` derives it from
plan/result artifacts.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from xiaot.models import Task, TaskPhase, derive_phase


class Orchestrator:
    """Coordinates task -> memory/skill/spec -> context -> (agent) -> settle.

    Ports (ports.py): memory (MemoryService), skills (SkillService),
    spec (SpecService), store (WorkspaceStore), context (ContextBuilder),
    runtime (RuntimeAdapter - reserved: in the MVP the calling agent executes
    in-session, xiaot never spawns a headless process).
    """

    def __init__(
        self,
        root: Path | None = None,
        memory: Any | None = None,
        skills: Any | None = None,
        spec: Any | None = None,
        store: Any | None = None,
        context: Any | None = None,
        runtime: Any | None = None,
    ) -> None:
        self._root = root
        self._memory = memory
        self._skills = skills
        self._spec = spec
        self._store = store
        self._context = context
        self._runtime = runtime

    # ---- root resolution -------------------------------------------------
    def _root_dir(self) -> Path:
        if self._root:
            return self._root
        return self._resolve_root()

    @staticmethod
    def _resolve_root() -> Path:
        """Resolve project root: env XIAOT_PROJECT > cwd (upward for a real
        project marker). A project marker is `.agent` (memory store) or a
        `.xiaot` that actually holds workspace/. HOME is never a project root."""
        env = os.environ.get("XIAOT_PROJECT")
        if env:
            return Path(env)
        home = str(Path.home()).lower()
        p = Path.cwd()
        while p:
            if str(p).lower() == home:
                break
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

    @staticmethod
    def _new_task_id() -> str:
        return f"task-{uuid.uuid4().hex[:8]}"

    # ---- lifecycle: phase derivation (single source of truth = artifacts) --
    def phase_of(self, task_id: str) -> TaskPhase:
        """Derive the task phase from workspace artifacts (never a redundant
        record): plan.json presence + result.md status via the store port."""
        root = self._root_dir()
        store = self._require("_store", "WorkspaceStore")
        if not store.workspace_exists(root, task_id):
            return TaskPhase.PLANNING
        state = store.read_workspace(root, task_id)
        has_plan = "plan" in state
        has_result = state.get("has_result", False)
        status = store.read_result_status(root, task_id) if has_result else None
        return derive_phase(has_plan, has_result, status)

    def _require(self, attr: str, port_name: str) -> Any:
        obj = getattr(self, attr)
        if obj is None:
            raise RuntimeError(
                f"Orchestrator not assembled: {port_name} port missing; "
                "use xiaot.orchestrator.assemble_default(root=...) or inject ports")
        return obj

    def _project(self, root: Path, project: str | None) -> str | None:
        """Resolve the effective project name.

        An explicit --project always wins. Otherwise fall back to the name
        pinned at `xiaot init` (.xiaot/project.json), so sessions that omit
        --project still share one project scope for memory. None when neither
        is present (pre-init temp roots behave as before).
        """
        if project:
            return project
        try:
            return self._require("_store", "WorkspaceStore").read_project_name(root)
        except Exception:
            return None

    # ---- use cases ---------------------------------------------------------
    def run_task(self, prompt: str, project: str | None = None,
                 session: str | None = None, resume: str | None = None,
                 budget: int = 5) -> dict[str, Any]:
        """Open the orchestration loop for one task (new or resumed).

        planning -> ready: memory retrieval, skill routing, spec decision and
        the context fragment (instruction + summaries + refs) are produced and
        snapshotted. Execution itself stays with the calling agent; settle
        closes the loop. Returns the same JSON surface as the v3.0 `task`
        command plus `phase` (state machine view, == derived phase).
        """
        root = self._root_dir()
        store = self._require("_store", "WorkspaceStore")
        project = self._project(root, project)

        if resume:
            try:
                exists = store.workspace_exists(root, resume)
            except ValueError as exc:
                return {"ok": False, "error": str(exc)}
            if not exists:
                return {"ok": False,
                        "error": f"workspace for {resume} not found"}
            task_id = resume
            state = store.read_workspace(root, task_id)
            prompt = state.get("plan", {}).get("goal", prompt) or prompt
        else:
            task_id = self._new_task_id()
            plan = {"title": project or task_id, "goal": prompt,
                    "steps": ["analyze and execute per agent"],
                    "acceptance": "user confirms"}
            store.write_plan(root, task_id, plan)
            store.write_result(root, task_id, "planning", prompt)
            state = {"task_id": task_id, "plan": plan}

        # 1) memory capability (port)
        memory = self._require("_memory", "MemoryService").retrieve(
            root, {"id": task_id, "project": project, "session_id": session},
            budget=budget)

        # 2) skill + spec capabilities (ports)
        skills = self._require("_skills", "SkillService")
        skill_hints = skills.resolve(prompt) if skills else []
        spec = self._require("_spec", "SpecService")
        spec_dec = spec.should_spec(prompt)
        # spec is an advisory branch (decision + guidance), never a hard gate:
        # a flagged task proceeds on the base path and carries guidance to run
        # the (reused) spec workflow when the agent decides it fits.
        if spec_dec.get("needs_spec"):
            spec_dec["guidance"] = (
                "large task: run the spec workflow first (xiaot routes it) to "
                "produce proposal/specs/tasks before editing, or proceed on the "
                "base path if that is overkill"
            )
        else:
            spec_dec["guidance"] = None

        # 3) context fragment (port) + snapshot (store port)
        context = self._require("_context", "ContextBuilder").build(
            Task(id=task_id, prompt=prompt, project=project,
                 session_id=session),
            memory, skill_hints=skill_hints, spec_decision=spec_dec)
        store.write_context_snapshot(root, task_id, context)

        return {"ok": True, "command": "task", "task_id": task_id,
                "workspace": str(root / ".xiaot" / "workspace" / task_id),
                "memory": memory, "skills": skill_hints, "spec": spec_dec,
                "context": context, "state": state,
                "phase": self.phase_of(task_id).value}

    def retrieve(self, prompt: str, project: str | None = None,
                 session: str | None = None, budget: int = 5,
                 root: Path | None = None) -> dict[str, Any]:
        """Inject A-model task-relevant memory (thin use case)."""
        root = root or self._root_dir()
        project = self._project(root, project)
        task = {"id": self._new_task_id(), "project": project,
                "session_id": session}
        return {"command": "retrieve", "prompt": prompt,
                **self._require("_memory", "MemoryService").retrieve(
                    root, task, budget=budget)}

    def plan(self, prompt: str, goal: str | None = None,
             steps: list[str] | None = None, acceptance: str | None = None,
             project: str | None = None,
             root: Path | None = None) -> dict[str, Any]:
        """Produce and persist the plan document (thin use case)."""
        root = root or self._root_dir()
        project = self._project(root, project)
        task_id = self._new_task_id()
        plan_doc = {
            "title": project or task_id,
            "goal": goal or prompt,
            "steps": steps or ["analyze and execute per agent"],
            "acceptance": acceptance or "user confirms",
        }
        self._require("_store", "WorkspaceStore").write_plan(
            root, task_id, plan_doc)
        return {"command": "plan", "task_id": task_id,
                "plan_path": str(root / ".xiaot" / "workspace" / task_id
                                 / "plan.md"),
                "plan": plan_doc}

    def confirm(self, text: str, scope: str = "task",
                project: str | None = None, task_id: str | None = None,
                evidence: str | None = None,
                root: Path | None = None) -> dict[str, Any]:
        """Human-approved promotion into medium memory (manual gate)."""
        root = root or self._root_dir()
        project = self._project(root, project)
        return self._require("_memory", "MemoryService").confirm(
            root, text, scope=scope, project=project, task_id=task_id,
            evidence=evidence)

    def settle(self, task_id: str, status: str = "success", output: str = "",
               candidates: list[dict[str, Any]] | None = None,
               root: Path | None = None) -> dict[str, Any]:
        """Close the loop: persist the outcome, then compare memory candidates
        and return suggestions. All promotions stay manual (human `confirm`)."""
        root = root or self._root_dir()
        store = self._require("_store", "WorkspaceStore")
        memory = self._require("_memory", "MemoryService")
        try:
            exists = store.workspace_exists(root, task_id)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if not exists:
            return {"ok": False,
                    "error": f"workspace for {task_id} not found "
                             "(run xiaot task first)"}
        store.write_result(root, task_id, status, output)
        suggestions = memory.suggest_settle(root, task_id, candidates)
        return {"command": "settle", "task_id": task_id, "status": status,
                "phase": self.phase_of(task_id).value, **suggestions}


# ---- default assembly (ports <- current implementations) -------------------
def assemble_default(root: Path | None = None) -> Orchestrator:
    """Assemble the Orchestrator with the current concrete implementations.

    The core stays decoupled: this is the one place that knows the concrete
    adapters (memory_service / skill_router / spec_router / spec_adapter /
    workspace / commands.build_context). Deliberately lazy imports keep the
    module graph acyclic (commands imports orchestrator for thinning).
    """
    from xiaot import memory_service, skill_router, spec_adapter, spec_router, workspace

    class _SpecService:
        """SpecService default: decision lives in spec_router, availability
        (CLI probe) in spec_adapter."""

        def should_spec(self, prompt: str) -> dict[str, Any]:
            return spec_router.should_spec(prompt)

        def available(self) -> bool:
            return spec_adapter.available()

    class _ContextBuilder:
        """ContextBuilder default: the shared build_context assembler."""

        def build(self, task: Task, memory: dict[str, Any],
                  skill_hints: list[dict[str, Any]] | None = None,
                  spec_decision: dict[str, Any] | None = None) -> dict[str, Any]:
            from xiaot.commands import build_context
            return build_context(task, memory, skill_hints=skill_hints,
                                 spec_decision=spec_decision)

    return Orchestrator(root=root, memory=memory_service, skills=skill_router,
                        spec=_SpecService(), store=workspace,
                        context=_ContextBuilder())

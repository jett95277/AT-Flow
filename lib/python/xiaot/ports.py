"""Domain ports (v3.1 layering).

Ports are the contracts between the orchestration core and external
capabilities. The core depends only on these Protocols; concrete adapters
(now the existing modules) are injected at assembly time. Cross-module
interaction must go through a port, never a direct import into the core.

Three peer capabilities sit below the orchestrator (same level):
  memory  - what has been validated (A-model medium/long)
  skill   - how to do this kind of task (guidance)
  spec    - which spec workflow a large task must follow (reused)

Method names/signatures mirror the current concrete modules where possible so
those modules duck-type the ports without an adapter shim; where the concrete
shape differs (ContextBuilder: `build` vs the module-level build_context
function; SpecService: availability probe lives in spec_adapter) the default
assembly in orchestrator.assemble_default adds a thin adapter. Replacing an
implementation later only has to honour these signatures.
"""

from __future__ import annotations

from typing import Any, Protocol

from xiaot.models import Result


class MemoryService(Protocol):
    """Memory capability: retrieve validated knowledge + manual settling."""

    def retrieve(self, root: Any, task: dict[str, Any],
                 budget: int = 5) -> dict[str, Any]: ...

    def suggest_settle(self, root: Any, task_id: str,
                       candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]: ...

    def confirm(self, root: Any, text: str, scope: str = "task",
                project: str | None = None, task_id: str | None = None,
                evidence: str | None = None) -> dict[str, Any]: ...


class SkillService(Protocol):
    """Skill capability: route guidance for a task."""

    def resolve(self, prompt: str, limit: int = 3) -> list[dict[str, Any]]: ...


class SpecService(Protocol):
    """Spec capability: decide + drive the (reused) spec workflow."""

    def should_spec(self, prompt: str) -> dict[str, Any]: ...

    def available(self) -> bool: ...


class ContextBuilder(Protocol):
    """Assemble the context fragment (instruction + summaries + refs)."""

    def build(self, task: Any, memory: dict[str, Any],
              skill_hints: list[dict[str, Any]] | None = None,
              spec_decision: dict[str, Any] | None = None) -> dict[str, Any]: ...


class WorkspaceStore(Protocol):
    """Task in-flight state store (.xiaot/workspace/<task-id>)."""

    def write_plan(self, root: Any, task_id: str, plan: dict[str, Any]) -> Any: ...

    def write_context_snapshot(self, root: Any, task_id: str,
                               context: dict[str, Any]) -> Any: ...

    def write_result(self, root: Any, task_id: str, status: str,
                     output: str) -> Any: ...

    def read_result_status(self, root: Any, task_id: str) -> str | None: ...

    def workspace_exists(self, root: Any, task_id: str) -> bool: ...

    def read_workspace(self, root: Any, task_id: str) -> dict[str, Any]: ...

    def read_project_name(self, root: Any) -> str | None: ...


class RuntimeAdapter(Protocol):
    """Execution capability: hand the context fragment to the executing
    agent. In the MVP the caller agent executes in-session; this port is the
    contract for a real (headless) execution path later."""

    def execute(self, context: Any) -> Result: ...

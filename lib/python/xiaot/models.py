"""Domain data models for the orchestration layer (S0 core).

Aligns with openspec change v3-orchestrator-mvp, capability orchestration/*.
S0 ships the minimal core: Task, Result, ContextPack, RuntimeStatus.
Full Context* types (memory/skill/spec) arrive with their orchestrators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeStatus(str, Enum):
    """Result lifecycle states (spec orchestration/runtime)."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class TaskPhase(str, Enum):
    """Task phase derived from plan artifacts + result (spec orchestration/task-lifecycle).

    Note: EXECUTING is carried by the calling agent in-session; it is not
    derivable from workspace artifacts, so derive_phase never returns it.
    """

    PLANNING = "planning"          # plan artifacts not ready
    READY = "ready"                # plan ready, awaiting confirmation/injection
    EXECUTING = "executing"        # handed to runtime (in-session, not derived)
    COMPLETED = "completed"        # result success/partial
    FAILED = "failed"              # result failed/cancelled


# v3.1 design names the in-process state machine TaskState; TaskPhase is the
# derived phase view over the same states. Keep one enum, alias the name so
# both descriptions refer to the same states (no drift).
TaskState = TaskPhase


def derive_phase(has_plan: bool, has_result: bool, result_status: str | None = None) -> TaskPhase:
    """Derive task phase from workspace artifacts (single source of truth).

    Rules (aligned with spec orchestration/task-lifecycle):
      - no plan        -> planning
      - plan, no result -> ready
      - result ok/partial -> completed ; failed/cancelled -> failed
    """
    if not has_plan:
        return TaskPhase.PLANNING
    if not has_result:
        return TaskPhase.READY
    if result_status in (RuntimeStatus.SUCCESS.value, RuntimeStatus.PARTIAL.value):
        return TaskPhase.COMPLETED
    if result_status in (RuntimeStatus.FAILED.value, RuntimeStatus.CANCELLED.value):
        return TaskPhase.FAILED
    # planning/executing placeholder or unparsable -> plan ready, not yet run
    return TaskPhase.READY


@dataclass
class Task:
    """A user task. Carries description + ownership; NEVER embeds memory/skill/spec bodies."""

    id: str
    prompt: str
    project: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Result:
    """Standardized execution result (contract between orchestrator and runtime)."""

    task_id: str
    status: RuntimeStatus
    output: str = ""
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextPack:
    """The single injection contract handed to the runtime.

    S0 carries task + constraints + metadata; memory/skills/spec contexts join in later steps.
    """

    task: Task
    constraints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    memory: list[dict[str, Any]] = field(default_factory=list)
    skills: list[dict[str, str]] = field(default_factory=list)
    spec: dict[str, Any] | None = None

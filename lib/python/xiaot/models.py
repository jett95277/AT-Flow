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
    """Task phase derived from plan artifacts + result (spec orchestration/task-lifecycle)."""

    PLANNING = "planning"          # plan artifacts not ready
    READY = "ready"                # plan ready, awaiting confirmation/injection
    EXECUTING = "executing"        # handed to runtime
    COMPLETED = "completed"        # result success/partial
    FAILED = "failed"              # result failed/cancelled


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

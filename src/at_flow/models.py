from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any


AGENT_ORDER = ("main", "analysis", "code", "test")
STEP_STATUSES = ("queued", "running", "retrying", "done", "failed", "aborted")

ROLE_GOALS: dict[str, str] = {
    "main": "Frame the user request, define boundaries, and produce acceptance criteria.",
    "analysis": "Create the execution plan, assumptions, risks, and handoff notes.",
    "code": "Perform the implementation work or produce exact implementation instructions.",
    "test": "Verify behavior, record test evidence, and write the final report.",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_session_id(task: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", task.lower()).strip("-")
    slug = slug[:36] or "session"
    return f"{stamp}-{slug}"


@dataclass
class StepState:
    agent: str
    status: str = "queued"
    started_at: str | None = None
    finished_at: str | None = None
    artifact_path: str | None = None
    error: str | None = None
    failure_reason: str | None = None
    retry_count: int = 0
    max_retries: int = 1
    retryable: bool = True
    input_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "artifact_path": self.artifact_path,
            "error": self.error,
            "failure_reason": self.failure_reason,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "retryable": self.retryable,
            "input_paths": self.input_paths,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepState":
        return cls(
            agent=data["agent"],
            status=data.get("status", "queued"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            artifact_path=data.get("artifact_path"),
            error=data.get("error"),
            failure_reason=data.get("failure_reason"),
            retry_count=int(data.get("retry_count", 0)),
            max_retries=int(data.get("max_retries", 1)),
            retryable=bool(data.get("retryable", True)),
            input_paths=list(data.get("input_paths", [])),
        )


@dataclass
class SessionState:
    schema_version: int
    id: str
    task: str
    project_path: str
    provider: str
    created_at: str
    updated_at: str
    status: str = "queued"
    current_stage: str | None = None
    failure_reason: str | None = None
    steps: list[StepState] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        task: str,
        project_path: Path,
        provider: str,
        pipeline: list[str] | tuple[str, ...] = AGENT_ORDER,
        session_id: str | None = None,
    ) -> "SessionState":
        return cls(
            schema_version=1,
            id=session_id or make_session_id(task),
            task=task,
            project_path=str(project_path.resolve()),
            provider=provider,
            created_at=now_iso(),
            updated_at=now_iso(),
            status="queued",
            current_stage=pipeline[0] if pipeline else None,
            failure_reason=None,
            steps=[StepState(agent=agent) for agent in pipeline],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "task": self.task,
            "project_path": self.project_path,
            "provider": self.provider,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "current_stage": self.current_stage,
            "failure_reason": self.failure_reason,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            id=data["id"],
            task=data["task"],
            project_path=data["project_path"],
            provider=data.get("provider", "mock"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            status=data.get("status", _infer_status(data.get("steps", []))),
            current_stage=data.get("current_stage"),
            failure_reason=data.get("failure_reason"),
            steps=[StepState.from_dict(item) for item in data.get("steps", [])],
        )

    def next_step_index(self) -> int | None:
        for index, step in enumerate(self.steps):
            if step.status in ("queued", "running", "retrying"):
                return index
        return None

    def is_complete(self) -> bool:
        return self.status == "done" or all(step.status == "done" for step in self.steps)

    def has_failed(self) -> bool:
        return self.status == "failed" or any(step.status == "failed" for step in self.steps)

    def interrupted_steps(self) -> list[int]:
        return [index for index, step in enumerate(self.steps) if step.status == "running"]

    def prior_artifacts(self, before_index: int) -> list[tuple[str, str]]:
        artifacts: list[tuple[str, str]] = []
        for step in self.steps[:before_index]:
            if step.artifact_path:
                artifacts.append((step.agent, step.artifact_path))
        return artifacts


def _infer_status(raw_steps: list[dict[str, Any]]) -> str:
    statuses = [step.get("status", "queued") for step in raw_steps]
    if any(status == "failed" for status in statuses):
        return "failed"
    if statuses and all(status == "done" for status in statuses):
        return "done"
    if any(status == "running" for status in statuses):
        return "running"
    return "queued"

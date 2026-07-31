from __future__ import annotations

from typing import Any


SESSION_SCHEMA_VERSION = 1
SESSION_STATUSES = {"queued", "running", "done", "failed", "aborted"}
STEP_STATUSES = {"queued", "running", "retrying", "done", "failed", "aborted"}


class SchemaValidationError(ValueError):
    pass


def validate_session_state(data: dict[str, Any]) -> None:
    _require(data, "schema_version", int)
    if data["schema_version"] != SESSION_SCHEMA_VERSION:
        raise SchemaValidationError(f"Unsupported schema_version: {data['schema_version']}")

    for key in ("id", "task", "project_path", "provider", "created_at", "updated_at"):
        _require(data, key, str)
    _require(data, "status", str)
    if data["status"] not in SESSION_STATUSES:
        raise SchemaValidationError(f"Invalid session status: {data['status']}")
    if data.get("current_stage") is not None and not isinstance(data["current_stage"], str):
        raise SchemaValidationError("current_stage must be a string or null")
    if data.get("failure_reason") is not None and not isinstance(data["failure_reason"], str):
        raise SchemaValidationError("failure_reason must be a string or null")

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise SchemaValidationError("steps must be a non-empty list")
    for index, step in enumerate(steps):
        _validate_step(index, step)


def _validate_step(index: int, step: Any) -> None:
    if not isinstance(step, dict):
        raise SchemaValidationError(f"step[{index}] must be an object")
    _require(step, "agent", str)
    _require(step, "status", str)
    if step["status"] not in STEP_STATUSES:
        raise SchemaValidationError(f"Invalid step status for {step['agent']}: {step['status']}")
    _require(step, "retry_count", int)
    _require(step, "max_retries", int)
    _require(step, "retryable", bool)
    if step["retry_count"] < 0:
        raise SchemaValidationError("retry_count must be >= 0")
    if step["max_retries"] < 0:
        raise SchemaValidationError("max_retries must be >= 0")
    if not isinstance(step.get("input_paths", []), list):
        raise SchemaValidationError("input_paths must be a list")
    for key in ("started_at", "finished_at", "artifact_path", "error", "failure_reason"):
        if step.get(key) is not None and not isinstance(step[key], str):
            raise SchemaValidationError(f"{key} must be a string or null")


def _require(data: dict[str, Any], key: str, expected_type: type) -> None:
    if key not in data:
        raise SchemaValidationError(f"Missing required key: {key}")
    if not isinstance(data[key], expected_type):
        raise SchemaValidationError(f"{key} must be {expected_type.__name__}")

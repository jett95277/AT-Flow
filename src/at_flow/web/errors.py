from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ApiErrorCode = Literal[
    "runtime_not_initialized",
    "session_not_found",
    "invalid_transition",
    "step_failed",
    "step_interrupted",
    "artifact_invalid",
    "file_not_allowed",
    "provider_unavailable",
    "internal_error",
]


@dataclass(frozen=True)
class ApiError(Exception):
    code: ApiErrorCode
    message: str
    retryable: bool
    details: dict[str, object] | None = None


def api_error_response(error: ApiError) -> dict[str, object]:
    body: dict[str, object] = {
        "code": error.code,
        "message": error.message,
        "retryable": error.retryable,
    }
    if error.details is not None:
        body["details"] = error.details
    return {"error": body}

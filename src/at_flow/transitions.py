from __future__ import annotations

from .models import SessionState, now_iso


class TransitionError(RuntimeError):
    pass


ALLOWED_TRANSITIONS = {
    "queued": {"running"},
    "retrying": {"running"},
    "running": {"done", "failed"},
    "failed": {"retrying", "aborted"},
    "done": set(),
    "aborted": set(),
}


def transition_step(
    session: SessionState,
    step_index: int,
    new_status: str,
    *,
    artifact_path: str | None = None,
    error: str | None = None,
    retryable: bool | None = None,
) -> None:
    step = session.steps[step_index]
    if new_status not in ALLOWED_TRANSITIONS.get(step.status, set()):
        raise TransitionError(f"Invalid transition for {step.agent}: {step.status} -> {new_status}")

    if new_status == "running":
        step.status = "running"
        step.started_at = now_iso()
        step.finished_at = None
        step.error = None
        step.failure_reason = None
    elif new_status == "done":
        step.status = "done"
        step.finished_at = now_iso()
        if artifact_path:
            step.artifact_path = artifact_path
        step.error = None
        step.failure_reason = None
        step.retryable = False
    elif new_status == "failed":
        step.status = "failed"
        step.finished_at = now_iso()
        step.error = error or "step failed"
        step.failure_reason = step.error
        if retryable is not None:
            step.retryable = retryable
        if artifact_path:
            step.artifact_path = artifact_path
    elif new_status == "retrying":
        _mark_retrying(session, step_index)
    elif new_status == "aborted":
        step.status = "aborted"
        step.finished_at = now_iso()
        step.retryable = False

    refresh_session_status(session)


def retry_failed_step(session: SessionState, step_index: int) -> None:
    step = session.steps[step_index]
    if step.status != "failed":
        raise TransitionError(f"Cannot retry non-failed step: {step.agent}")
    if not step.retryable:
        raise TransitionError(f"Step is not retryable: {step.agent}")
    if step.retry_count >= step.max_retries:
        raise TransitionError(f"Retry limit reached for {step.agent}")
    transition_step(session, step_index, "retrying")


def recover_interrupted_step(session: SessionState, step_index: int, reason: str) -> None:
    step = session.steps[step_index]
    if step.status != "running":
        raise TransitionError(f"Cannot recover non-running step: {step.agent}")
    transition_step(session, step_index, "failed", error=f"Interrupted step recovered: {reason}", retryable=True)


def refresh_session_status(session: SessionState) -> None:
    failed = _first_step_with_status(session, "failed")
    if failed is not None:
        session.status = "failed"
        session.current_stage = session.steps[failed].agent
        session.failure_reason = session.steps[failed].failure_reason
        return

    if all(step.status == "done" for step in session.steps):
        session.status = "done"
        session.current_stage = None
        session.failure_reason = None
        return

    running = _first_step_with_status(session, "running")
    if running is not None:
        session.status = "running"
        session.current_stage = session.steps[running].agent
        session.failure_reason = None
        return

    retrying = _first_step_with_status(session, "retrying")
    if retrying is not None:
        session.status = "running"
        session.current_stage = session.steps[retrying].agent
        session.failure_reason = None
        return

    next_index = session.next_step_index()
    session.status = "queued"
    session.current_stage = session.steps[next_index].agent if next_index is not None else None
    session.failure_reason = None


def _mark_retrying(session: SessionState, step_index: int) -> None:
    step = session.steps[step_index]
    step.status = "retrying"
    step.retry_count += 1
    step.started_at = None
    step.finished_at = None
    step.error = None
    step.failure_reason = None
    step.artifact_path = None


def _first_step_with_status(session: SessionState, status: str) -> int | None:
    for index, step in enumerate(session.steps):
        if step.status == status:
            return index
    return None

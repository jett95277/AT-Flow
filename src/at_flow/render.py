from __future__ import annotations

from .models import SessionState, StepState


STATUS_LABELS = {
    "queued": "WAIT",
    "running": "RUN",
    "done": "OK",
    "failed": "FAIL",
}

CHAT_STATUS_LABELS = {
    "queued": "queued",
    "running": "running",
    "done": "done",
    "failed": "failed",
}

CHAT_ROLE_LABELS = {
    "main": "task boundary",
    "analysis": "plan and risk",
    "code": "implementation",
    "test": "verification",
}


def render_step(step: StepState) -> str:
    label = STATUS_LABELS.get(step.status, step.status.upper())
    return f"{step.agent}:{label}"


def render_session(session: SessionState) -> str:
    machine = " -> ".join(render_step(step) for step in session.steps)
    lines = [
        f"AT {session.id}",
        f"task: {session.task}",
        f"provider: {session.provider}",
        f"project: {session.project_path}",
        f"state: {machine}",
    ]
    if session.has_failed():
        for step in session.steps:
            if step.status == "failed" and step.error:
                lines.append(f"error[{step.agent}]: {step.error}")
    return "\n".join(lines)


def render_session_row(session: SessionState) -> str:
    return f"{session.id}  {_session_status_label(session):8}  {session.provider:8}  {session.task}"


def render_chat_session(session: SessionState) -> str:
    current_index, current_step = _current_chat_step(session)
    lines = [
        "**AT Control Panel**",
        "",
        "**AT State Machine**",
        "```text",
        _render_ascii_machine(session.steps),
        "```",
        "",
        "**Current Stage**",
        "```text",
        _render_current_stage(session, current_index, current_step),
        "```",
        "",
        "**Stage Details**",
        "```text",
        _ascii_table(
            ["agent", "state", "role", "artifact"],
            [
                [
                    step.agent,
                    CHAT_STATUS_LABELS.get(step.status, step.status),
                    CHAT_ROLE_LABELS.get(step.agent, step.agent),
                    _artifact_label(step),
                ]
                for step in session.steps
            ],
        ),
        "```",
        "",
        "**Codex Execution Layer**",
        "```text",
        _ascii_kv(
            [
                ("provider", session.provider),
                ("role", "executor controlled by AT state machine"),
                ("boundary", "agent.md + permissions.json + output.md"),
            ]
        ),
        "```",
    ]
    if session.has_failed():
        lines.extend(["", "**Errors**", "```text"])
        for step in session.steps:
            if step.status == "failed" and step.error:
                lines.append(f"{step.agent}: {step.error}")
        lines.append("```")
    return "\n".join(lines)


def render_chat_panel(sessions: list[SessionState]) -> str:
    latest = sessions[-1] if sessions else None
    lines = [
        "```text",
        _render_startup_banner(),
        "```",
        "```text",
        _render_idle_machine(),
        "```",
        "",
        "**Current Session**",
        "```text",
        _render_panel_current_session(latest),
        "```",
        "",
        "**Command Menu**",
        "```text",
        _ascii_table(
            ["command", "action"],
            [
                ["AT:", "open this control panel"],
                ["AT: init", "initialize AT workspace"],
                ["AT: start task, <task>", "create a new session"],
                ["AT: next", "run one agent step"],
                ["AT: continue", "run until done or failed"],
                ["AT: retry", "retry the first failed step"],
                ["AT: status", "show current session"],
                ["AT: list", "show all sessions"],
                ["AT: artifact <agent>", "show agent output"],
                ["AT: audit", "show audit report"],
            ],
        ),
        "```",
        "",
        "**Codex Execution Layer**",
        "```text",
        _ascii_kv(
            [
                ("provider", "not selected"),
                ("role", "waiting for AT command"),
                ("boundary", "AT state machine must be shown before execution"),
            ]
        ),
        "```",
    ]
    return "\n".join(lines)


def render_chat_session_row(session: SessionState) -> str:
    return f"| `{session.id}` | `{_session_status_label(session)}` | `{session.provider}` | {session.task} |"


def render_chat_session_table(sessions: list[SessionState]) -> str:
    return "\n".join(
        [
            "**AT Sessions**",
            "```text",
            _ascii_table(
                ["session", "state", "provider", "task"],
                [
                    [
                        session.id,
                        _session_status_label(session),
                        session.provider,
                        session.task,
                    ]
                    for session in sessions
                ],
            ),
            "```",
        ]
    )


def _current_chat_step(session: SessionState) -> tuple[int, StepState]:
    for index, step in enumerate(session.steps):
        if step.status == "failed":
            return index, step
    for index, step in enumerate(session.steps):
        if step.status == "running":
            return index, step
    next_index = session.next_step_index()
    if next_index is not None:
        return next_index, session.steps[next_index]
    return len(session.steps) - 1, session.steps[-1]


def _render_current_stage(session: SessionState, index: int, step: StepState) -> str:
    input_label = "user task"
    if index > 0:
        input_label = _artifact_label(session.steps[index - 1])
    return _ascii_kv(
        [
            ("session", session.id),
            ("task", session.task),
            ("project", session.project_path),
            ("agent", step.agent),
            ("state", CHAT_STATUS_LABELS.get(step.status, step.status)),
            ("role", CHAT_ROLE_LABELS.get(step.agent, step.agent)),
            ("input", input_label),
            ("output", f"agents/{step.agent}/outbox/artifact.md"),
        ]
    )


def _render_idle_machine() -> str:
    return "\n".join(
        [
            "AT STATE MACHINE",
            "",
            "+----------+     +----------+     +----------+     +----------+",
            "| main     | --> | analysis | --> | code     | --> | test     |",
            "| standby  |     | standby  |     | standby  |     | standby  |",
            "+----------+     +----------+     +----------+     +----------+",
        ]
    )


def _render_startup_banner() -> str:
    return "\n".join(
        [
            "+------------------------------------------------------------+",
            "| AT FLOW                                                    |",
            "| Multi-Agent Control Runtime                                |",
            "+------------------------------------------------------------+",
            "| mode      : conversation control panel                     |",
            "| trigger   : AT                                             |",
            "| interface : ASCII state console                            |",
            "| runtime   : ready                                          |",
            "+------------------------------------------------------------+",
        ]
    )


def _render_panel_current_session(session: SessionState | None) -> str:
    if session is None:
        return _ascii_kv(
            [
                ("session", "<none>"),
                ("state", "ready"),
                ("next", "AT: start task, <task>"),
            ]
        )
    return _ascii_kv(
        [
            ("session", session.id),
            ("state", _session_status_label(session)),
            ("task", session.task),
            ("next", _next_panel_action(session)),
        ]
    )


def _render_ascii_machine(steps: list[StepState]) -> str:
    boxes = [_machine_box(step) for step in steps]
    separators = ["     ", " --> ", "     "]
    lines: list[str] = []
    for line_index in range(3):
        lines.append(separators[line_index].join(box[line_index] for box in boxes))
    return "\n".join(lines)


def _machine_box(step: StepState) -> list[str]:
    status = CHAT_STATUS_LABELS.get(step.status, step.status)
    width = max(len(step.agent), len(status), 8)
    return [
        "+" + "-" * (width + 2) + "+",
        "| " + step.agent.ljust(width) + " |",
        "| " + status.ljust(width) + " |",
    ]


def _ascii_table(headers: list[str], rows: list[list[str]]) -> str:
    values = [[str(cell) for cell in row] for row in rows]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in values)) if values else len(headers[index])
        for index in range(len(headers))
    ]
    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    header = "|" + "|".join(" " + headers[index].ljust(widths[index]) + " " for index in range(len(headers))) + "|"
    body = [
        "|" + "|".join(" " + row[index].ljust(widths[index]) + " " for index in range(len(headers))) + "|"
        for row in values
    ]
    return "\n".join([border, header, border, *body, border])


def _ascii_kv(items: list[tuple[str, object]]) -> str:
    key_width = max(len(key) for key, _ in items)
    return "\n".join(f"{key.ljust(key_width)} : {value}" for key, value in items)


def _artifact_label(step: StepState) -> str:
    if step.artifact_path:
        marker = "\\agents\\"
        if marker in step.artifact_path:
            return "agents/" + step.artifact_path.split(marker, 1)[1].replace("\\", "/")
        return step.artifact_path
    if step.status == "running":
        return "generating"
    if step.status == "failed":
        return "failed"
    return "waiting"


def _session_status_label(session: SessionState) -> str:
    if session.has_failed():
        return "failed"
    if session.is_complete():
        return "done"
    next_index = session.next_step_index()
    if next_index is None:
        return "unknown"
    return f"next:{session.steps[next_index].agent}"


def _next_panel_action(session: SessionState) -> str:
    if session.has_failed():
        return "AT: status or AT: audit"
    if session.is_complete():
        return "AT: start task, <task>"
    return "AT: next or AT: continue"

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .providers import check_provider_capability
from .trace import read_trace_events
from .workspace import ATWorkspace, WorkspaceError


def session_trace_summary(workspace: ATWorkspace, session_id: str) -> list[dict[str, Any]]:
    return read_trace_events(workspace.session_dir(session_id) / "trace.jsonl")


def render_trace_summary(events: list[dict[str, Any]]) -> str:
    if not events:
        return "no trace events"
    lines = ["trace events:"]
    for event in events:
        agent = event.get("agent") or "-"
        status = event.get("status") or "-"
        detail = event.get("detail") or ""
        lines.append(f"{event.get('event')}  agent:{agent}  status:{status}  {detail}".rstrip())
    return "\n".join(lines)


def session_audit_summary(workspace: ATWorkspace, session_id: str) -> list[dict[str, Any]]:
    audit_dir = workspace.session_dir(session_id) / "audit"
    if not audit_dir.exists():
        return []
    reports: list[dict[str, Any]] = []
    for path in sorted(audit_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            report = json.load(handle)
        report["file"] = path.name
        reports.append(report)
    return reports


def render_audit_summary(reports: list[dict[str, Any]]) -> str:
    if not reports:
        return "no audit reports"
    lines = ["audit reports:"]
    for report in reports:
        violations = report.get("violations", [])
        lines.append(f"{report['file']}  agent:{report.get('agent', '-')}  violations: {len(violations)}")
        for violation in violations:
            lines.append(
                f"  - {violation.get('group')}:{violation.get('change')}:{violation.get('path')}"
            )
    return "\n".join(lines)


def session_artifact_text(workspace: ATWorkspace, session_id: str, agent: str) -> str:
    outbox = workspace.session_agent_outbox_dir(session_id, agent)
    artifact = outbox / "artifact.md"
    if artifact.exists():
        return artifact.read_text(encoding="utf-8")
    failure = outbox / "failure.json"
    if failure.exists():
        return failure.read_text(encoding="utf-8")
    raise WorkspaceError(f"No artifact or failure for agent `{agent}` in session: {session_id}")


def doctor_checks(workspace: ATWorkspace) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    checks.append(("config", (workspace.root / "at.config.json").exists(), str(workspace.root / "at.config.json")))
    for agent in workspace.config.get("pipeline", []):
        ok = (
            workspace.agent_profile_path(agent).exists()
            and workspace.agent_permissions_path(agent).exists()
            and workspace.agent_output_path(agent).exists()
        )
        checks.append((f"agent:{agent}", ok, str(workspace.agents_root / agent)))

    running = [
        session.id
        for session in workspace.list_sessions()
        if any(step.status == "running" for step in session.steps)
    ]
    checks.append(("sessions_running", not running, ", ".join(running) if running else "none"))
    for name in sorted(workspace.config.get("providers", {})):
        capability = check_provider_capability(name, workspace.config)
        checks.append((f"provider:{name}", bool(capability["available"]), str(capability["detail"])))
    return checks


def render_doctor_checks(checks: list[tuple[str, bool, str]]) -> str:
    lines = ["doctor:"]
    for name, ok, detail in checks:
        lines.append(f"{name}: {'OK' if ok else 'FAIL'}  {detail}")
    return "\n".join(lines)

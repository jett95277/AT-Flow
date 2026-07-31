from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from typing import Any

from .artifacts import validate_artifact_contract
from .context_contracts import build_agent_context_contract, write_agent_context_contract
from .models import SessionState, now_iso
from .providers import AgentContext, ProviderError, build_prompt, make_provider
from .render import render_session
from .trace import append_trace_event
from .transitions import recover_interrupted_step, retry_failed_step, transition_step
from .workspace import ATWorkspace, WorkspaceError


class SessionLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: int | None = None

    def __enter__(self) -> "SessionLock":
        try:
            self.handle = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise WorkspaceError(f"Session is already running: {self.path.parent.name}") from exc
        os.write(self.handle, str(os.getpid()).encode("utf-8"))
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.handle is not None:
            os.close(self.handle)
            self.handle = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class Runner:
    def __init__(self, workspace: ATWorkspace, renderer=render_session) -> None:
        self.workspace = workspace
        self.renderer = renderer

    def run(self, session_id: str, provider_name: str | None = None, one_step: bool = False) -> SessionState:
        lock_path = self.workspace.session_dir(session_id) / ".lock"
        with SessionLock(lock_path):
            session = self.workspace.load_session(session_id)
            if provider_name:
                session.provider = provider_name
                self.workspace.save_session(session)
            if self._recover_interrupted_session(session):
                return session
            return self._run_loop(session, one_step=one_step)

    def retry(self, session_id: str, one_step: bool = False) -> SessionState:
        lock_path = self.workspace.session_dir(session_id) / ".lock"
        with SessionLock(lock_path):
            session = self.workspace.load_session(session_id)
            failed_index = _first_failed_step_index(session)
            if failed_index is None:
                raise WorkspaceError(f"Session has no failed step: {session_id}")
            retry_failed_step(session, failed_index)
            cleaned_paths = self._clear_retry_outbox(session, failed_index)
            self._trace(
                session.id,
                "retry_cleanup",
                agent=session.steps[failed_index].agent,
                step_index=failed_index,
                status="retrying",
                data={"cleaned_paths": cleaned_paths},
            )
            self._trace(session.id, "transition_state", agent=session.steps[failed_index].agent, step_index=failed_index, status="retrying")
            self.workspace.save_session(session)
            return self._run_loop(session, one_step=one_step)

    def _run_loop(self, session: SessionState, one_step: bool = False) -> SessionState:
        while True:
            index = session.next_step_index()
            if index is None or session.has_failed():
                break
            self._run_step(session, index)
            session = self.workspace.load_session(session.id)
            print(self.renderer(session))
            if one_step:
                break
        return session

    def _recover_interrupted_session(self, session: SessionState) -> bool:
        interrupted = session.interrupted_steps()
        if not interrupted:
            return False

        step_index = interrupted[0]
        step = session.steps[step_index]
        reason = "session contained a running step when Runner started"
        recover_interrupted_step(session, step_index, reason)
        self._trace(
            session.id,
            "recover_interrupted_step",
            agent=step.agent,
            step_index=step_index,
            status="failed",
            detail=reason,
        )
        self.workspace.save_session(session)
        return True

    def _clear_retry_outbox(self, session: SessionState, step_index: int) -> list[str]:
        step = session.steps[step_index]
        outbox = self.workspace.session_agent_outbox_dir(session.id, step.agent)
        outbox.mkdir(parents=True, exist_ok=True)
        cleaned: list[str] = []
        for item in sorted(outbox.iterdir()):
            cleaned.append(item.relative_to(outbox).as_posix())
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        for name in ("proposals", "logs"):
            (outbox / name).mkdir(parents=True, exist_ok=True)
        return cleaned

    def _run_step(self, session: SessionState, step_index: int) -> None:
        step = session.steps[step_index]
        if step.status == "done":
            return

        provider = make_provider(session.provider, self.workspace.config)
        session_dir = self.workspace.session_dir(session.id)
        agent_dir = self.workspace.session_agent_dir(session.id, step.agent)
        self._trace(session.id, "prepare_agent", agent=step.agent, step_index=step_index, status=step.status)
        self.workspace.prepare_agent_directories(session.id, step.agent)
        self.workspace.materialize_session_agent_package(session.id, step.agent)
        self._route_prior_artifacts_to_inbox(session, step_index)
        project_path = Path(session.project_path)
        project_path.mkdir(parents=True, exist_ok=True)

        context = AgentContext(
            workspace_root=self.workspace.root,
            shared_root=self.workspace.shared_root,
            session_dir=session_dir,
            agent_dir=agent_dir,
            agent_inbox_dir=self.workspace.session_agent_inbox_dir(session.id, step.agent),
            agent_outbox_dir=self.workspace.session_agent_outbox_dir(session.id, step.agent),
            agent_workspace_dir=self.workspace.session_agent_workspace_dir(session.id, step.agent),
            agent_profile_path=self.workspace.materialize_session_agent_profile(session.id, step.agent),
            agent_permissions_path=self.workspace.materialize_session_agent_permissions(session.id, step.agent),
            agent_output_path=self.workspace.materialize_session_agent_output(session.id, step.agent),
            agent_context_path=self.workspace.session_context_path(session.id, step.agent),
            project_path=project_path,
            session=session,
            step_index=step_index,
        )
        step.input_paths = [str(path.resolve()) for path in context.inbox_files]
        self._trace(
            session.id,
            "route_prior_handoff",
            agent=step.agent,
            step_index=step_index,
            status=step.status,
            data={"input_paths": step.input_paths},
        )
        context_path = write_agent_context_contract(context)
        self._trace(
            session.id,
            "build_context",
            agent=step.agent,
            step_index=step_index,
            status=step.status,
            data={"context_path": str(context_path.resolve())},
        )
        self._write_input_contract(context)
        prompt = build_prompt(context)
        (agent_dir / "prompt.md").write_text(prompt, encoding="utf-8")

        transition_step(session, step_index, "running")
        self._trace(session.id, "transition_state", agent=step.agent, step_index=step_index, status="running")
        self.workspace.save_session(session)

        baseline = self._snapshot_protected_paths(context)
        artifact_path: Path | None = None
        failure_error: str | None = None
        retryable = True
        self._trace(session.id, "run_agent_start", agent=step.agent, step_index=step_index, status="running")
        try:
            result = provider.run(context, prompt)
            artifact_path = self._collect_output(context, result.content)
            self._trace(session.id, "collect_output", agent=step.agent, step_index=step_index, status="running", data={"artifact_path": str(artifact_path.resolve())})
            missing_sections = validate_artifact_contract(
                step.agent,
                context.agent_output_path.read_text(encoding="utf-8"),
                artifact_path.read_text(encoding="utf-8"),
            )
            if missing_sections:
                failure_error = "Artifact contract failed: missing sections: " + ", ".join(missing_sections)
                artifact_path = self._write_failure_artifact(context, failure_error, retryable=True)
                self._trace(
                    session.id,
                    "artifact_contract_failed",
                    agent=step.agent,
                    step_index=step_index,
                    status="running",
                    detail=failure_error,
                    data={"missing_sections": missing_sections},
                )
            self._trace(session.id, "run_agent_done", agent=step.agent, step_index=step_index, status="running")
        except ProviderError as exc:
            failure_error = str(exc)
            artifact_path = self._write_failure_artifact(context, failure_error, retryable=True)
            self._trace(session.id, "collect_output", agent=step.agent, step_index=step_index, status="running", data={"artifact_path": str(artifact_path.resolve())})
            self._trace(session.id, "run_agent_failed", agent=step.agent, step_index=step_index, status="running", detail=failure_error)

        proposal_paths = self._collect_memory_proposals(context)
        self._trace(
            session.id,
            "collect_memory_proposals",
            agent=step.agent,
            step_index=step_index,
            status="running",
            data={"proposal_paths": [str(path.resolve()) for path in proposal_paths]},
        )

        audit_report = self._audit_permissions(context, baseline)
        self._trace(
            session.id,
            "audit_permissions",
            agent=step.agent,
            step_index=step_index,
            status="running",
            data={"violations": audit_report["violations"]},
        )
        if audit_report["violations"]:
            detail = _format_audit_error(audit_report["violations"])
            failure_error = f"Permission audit failed: {detail}"
            retryable = False
            artifact_path = self._write_failure_artifact(context, failure_error, retryable=retryable)
            self._trace(session.id, "collect_output", agent=step.agent, step_index=step_index, status="running", data={"artifact_path": str(artifact_path.resolve())})

        if failure_error:
            transition_step(
                session,
                step_index,
                "failed",
                artifact_path=str(artifact_path.resolve()) if artifact_path else None,
                error=failure_error,
                retryable=retryable,
            )
            self._trace(session.id, "transition_state", agent=step.agent, step_index=step_index, status="failed", detail=failure_error)
        else:
            transition_step(session, step_index, "done", artifact_path=str(artifact_path.resolve()) if artifact_path else None)
            self._trace(session.id, "transition_state", agent=step.agent, step_index=step_index, status="done")

        self.workspace.save_session(session)
        if step.status == "done":
            self._route_handoff(session, step_index)
            self._trace(session.id, "route_handoff", agent=step.agent, step_index=step_index, status="done")

    def _write_input_contract(self, context: AgentContext) -> Path:
        path = context.agent_dir / "input.json"
        data = build_agent_context_contract(context)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return path

    def _collect_output(self, context: AgentContext, content: str) -> Path:
        artifact_path = context.agent_outbox_dir / "artifact.md"
        if artifact_path.exists() and artifact_path.stat().st_size > 0:
            return artifact_path
        artifact_path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return artifact_path

    def _write_failure_artifact(self, context: AgentContext, error: str, *, retryable: bool) -> Path:
        failure_path = context.agent_outbox_dir / "failure.json"
        data = {
            "session_id": context.session.id,
            "agent": context.agent,
            "step_index": context.step_index,
            "status": "failed",
            "error": error,
            "retryable": retryable,
            "created_at": now_iso(),
        }
        failure_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return failure_path

    def _collect_memory_proposals(self, context: AgentContext) -> list[Path]:
        source_dir = context.agent_outbox_dir / "proposals"
        if not source_dir.exists():
            return []

        target_dir = self.workspace.session_memory_proposals_dir(context.session.id)
        target_dir.mkdir(parents=True, exist_ok=True)
        collected: list[Path] = []
        for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
            relative_name = source.relative_to(source_dir).as_posix().replace("/", "__")
            target = target_dir / f"{context.agent}-{relative_name}"
            shutil.copy2(source, target)
            collected.append(target)
        return collected

    def _route_prior_artifacts_to_inbox(self, session: SessionState, step_index: int) -> None:
        step = session.steps[step_index]
        inbox = self.workspace.session_agent_inbox_dir(session.id, step.agent)
        inbox.mkdir(parents=True, exist_ok=True)
        for index, prior_step in enumerate(session.steps[:step_index]):
            if not prior_step.artifact_path:
                continue
            source = Path(prior_step.artifact_path)
            if not source.exists():
                continue
            target = inbox / _handoff_name(index, prior_step.agent)
            shutil.copy2(source, target)

    def _route_handoff(self, session: SessionState, step_index: int) -> None:
        step = session.steps[step_index]
        if not step.artifact_path:
            return
        source = Path(step.artifact_path)
        if not source.exists():
            return

        handoff_dir = self.workspace.session_dir(session.id) / "handoff"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        handoff_path = handoff_dir / _handoff_name(step_index, step.agent)
        shutil.copy2(source, handoff_path)

        next_index = step_index + 1
        if next_index >= len(session.steps):
            return
        next_step = session.steps[next_index]
        next_inbox = self.workspace.session_agent_inbox_dir(session.id, next_step.agent)
        next_inbox.mkdir(parents=True, exist_ok=True)
        shutil.copy2(handoff_path, next_inbox / handoff_path.name)

    def _snapshot_protected_paths(self, context: AgentContext) -> dict[str, dict[str, dict[str, Any]]]:
        snapshots: dict[str, dict[str, dict[str, Any]]] = {
            "shared": _snapshot_path(context.shared_root),
            "project": _snapshot_path(context.project_path),
            "session_state": _snapshot_path(context.session_dir / "state.json"),
            "handoff": _snapshot_path(context.session_dir / "handoff"),
        }
        agents_dir = context.session_dir / "agents"
        if agents_dir.exists():
            for path in agents_dir.iterdir():
                if path.is_dir() and path.name != context.agent:
                    snapshots[f"other_agent:{path.name}"] = _snapshot_path(path)
        return snapshots

    def _audit_permissions(
        self,
        context: AgentContext,
        before: dict[str, dict[str, dict[str, Any]]],
    ) -> dict[str, Any]:
        permissions = _load_permissions(context.agent_permissions_path)
        write_permissions = permissions.get("write", {})
        violations: list[dict[str, str]] = []
        checked: list[str] = []

        for group, previous in before.items():
            current = _snapshot_path(_audit_group_path(context, group))
            checked.append(group)
            if _audit_group_allowed(group, write_permissions):
                continue
            for change in _diff_snapshots(previous, current):
                violations.append({"group": group, **change})

        report = {
            "session_id": context.session.id,
            "agent": context.agent,
            "checked_at": now_iso(),
            "checked": checked,
            "violations": violations,
        }
        audit_dir = context.session_dir / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = audit_dir / f"{context.step_index:02d}-{context.agent}.json"
        audit_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report

    def _trace(
        self,
        session_id: str,
        event: str,
        *,
        agent: str | None = None,
        step_index: int | None = None,
        status: str | None = None,
        detail: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        append_trace_event(
            self.workspace.session_dir(session_id) / "trace.jsonl",
            event,
            session_id=session_id,
            agent=agent,
            step_index=step_index,
            status=status,
            detail=detail,
            data=data,
        )


def _handoff_name(step_index: int, agent: str) -> str:
    return f"{step_index:02d}-{agent}-artifact.md"


def _first_failed_step_index(session: SessionState) -> int | None:
    for index, step in enumerate(session.steps):
        if step.status == "failed":
            return index
    return None


def _load_permissions(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _audit_group_path(context: AgentContext, group: str) -> Path:
    if group == "shared":
        return context.shared_root
    if group == "project":
        return context.project_path
    if group == "session_state":
        return context.session_dir / "state.json"
    if group == "handoff":
        return context.session_dir / "handoff"
    if group.startswith("other_agent:"):
        agent = group.split(":", 1)[1]
        return context.session_dir / "agents" / agent
    raise RuntimeError(f"Unknown audit group: {group}")


def _audit_group_allowed(group: str, write_permissions: dict[str, Any]) -> bool:
    if group == "shared":
        return bool(write_permissions.get("shared"))
    if group == "project":
        return bool(write_permissions.get("project"))
    if group in ("session_state", "handoff"):
        return bool(write_permissions.get("session_control"))
    if group.startswith("other_agent:"):
        return bool(write_permissions.get("other_agents"))
    return False


def _snapshot_path(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    if path.is_file():
        return {".": _path_signature(path)}

    snapshot: dict[str, dict[str, Any]] = {}
    for item in path.rglob("*"):
        rel = item.relative_to(path).as_posix()
        snapshot[rel] = _path_signature(item)
    return snapshot


def _path_signature(path: Path) -> dict[str, Any]:
    stat = path.stat()
    if path.is_dir():
        return {"type": "dir", "mtime_ns": stat.st_mtime_ns}
    return {
        "type": "file",
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _diff_snapshots(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    before_keys = set(before)
    after_keys = set(after)
    for path in sorted(after_keys - before_keys):
        changes.append({"change": "added", "path": path})
    for path in sorted(before_keys - after_keys):
        changes.append({"change": "removed", "path": path})
    for path in sorted(before_keys & after_keys):
        if before[path] != after[path]:
            changes.append({"change": "modified", "path": path})
    return changes


def _format_audit_error(violations: list[dict[str, str]]) -> str:
    preview = ", ".join(
        f"{item['group']}:{item['change']}:{item['path']}" for item in violations[:5]
    )
    if len(violations) > 5:
        preview += f", ... {len(violations) - 5} more"
    return preview

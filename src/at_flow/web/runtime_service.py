from __future__ import annotations

from typing import Any, Callable

from .errors import ApiError
from .schemas import CommandResultResponse
from ..engine import Runner
from ..inspectors import session_artifact_text, session_audit_summary, session_trace_summary
from ..models import SessionState
from ..workspace import ATWorkspace, WorkspaceError


class RuntimeService:
    def __init__(self, workspace: ATWorkspace) -> None:
        self.workspace = workspace

    def list_sessions(self) -> list[dict[str, Any]]:
        return [session.to_dict() for session in self.workspace.list_sessions()]

    def get_state(self, session_id: str) -> dict[str, Any]:
        return self._map_workspace_error(lambda: self.workspace.load_session(session_id).to_dict())

    def get_trace(self, session_id: str) -> list[dict[str, Any]]:
        return self._map_workspace_error(
            lambda: self._load_session_then(session_id, lambda: session_trace_summary(self.workspace, session_id))
        )

    def get_audit(self, session_id: str) -> list[dict[str, Any]]:
        return self._map_workspace_error(
            lambda: self._load_session_then(session_id, lambda: session_audit_summary(self.workspace, session_id))
        )

    def get_artifact(self, session_id: str, agent: str) -> str:
        return self._map_workspace_error(lambda: self._load_optional_artifact(session_id, agent))

    def create_session(
        self,
        *,
        task: str,
        provider: str = "mock",
        project: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        project_path = self.workspace.projects_root / "default" if project is None else self.workspace.root / project
        pipeline = self.workspace.config.get("pipeline", ["main", "analysis", "code", "test"])
        session = SessionState.new(
            task=task,
            project_path=project_path,
            provider=provider,
            pipeline=pipeline,
            session_id=session_id,
        )
        self._map_workspace_error(lambda: self.workspace.create_session(session))
        return CommandResultResponse(ok=True, session=session.to_dict()).to_dict()

    def run_one_step(self, session_id: str) -> dict[str, Any]:
        return self._run_command(lambda: Runner(self.workspace).run(session_id, one_step=True))

    def continue_session(self, session_id: str) -> dict[str, Any]:
        return self._run_command(lambda: Runner(self.workspace).run(session_id))

    def retry_session(self, session_id: str) -> dict[str, Any]:
        return self._run_command(lambda: Runner(self.workspace).retry(session_id))

    def _load_session_then(self, session_id: str, callback: Callable[[], Any]) -> Any:
        self.workspace.load_session(session_id)
        return callback()

    def _load_optional_artifact(self, session_id: str, agent: str) -> str:
        self.workspace.load_session(session_id)
        try:
            return session_artifact_text(self.workspace, session_id, agent)
        except WorkspaceError as exc:
            if str(exc).startswith("No artifact or failure"):
                return ""
            raise

    def _map_workspace_error(self, callback: Callable[[], Any]) -> Any:
        try:
            return callback()
        except WorkspaceError as exc:
            raise ApiError(
                code="session_not_found",
                message=str(exc),
                retryable=False,
            ) from exc

    def _run_command(self, callback: Callable[[], SessionState]) -> dict[str, Any]:
        session = self._map_workspace_error(callback)
        return CommandResultResponse(ok=not session.has_failed(), session=session.to_dict()).to_dict()

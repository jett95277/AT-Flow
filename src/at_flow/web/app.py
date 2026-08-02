from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .db import WebConsoleDb
from .errors import ApiError, api_error_response
from .runtime_service import RuntimeService
from .schemas import DoctorCheckResponse, HealthResponse
from .workspace_service import WorkspaceService
from ..config import ConfigError
from ..inspectors import doctor_checks
from ..workspace import ATWorkspace


_DEFAULT_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app(root: Path | str = ".") -> FastAPI:
    app = FastAPI(title="AT Flow Web Console API")
    workspace_root = Path(root).resolve()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins_from_env(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def record_request_history(request: Request, call_next):
        response = await call_next(request)
        if (workspace_root / "at.config.json").exists():
            WebConsoleDb(workspace_root / ".at" / "web" / "console.sqlite3").record_request(
                request.method,
                request.url.path,
                response.status_code,
            )
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(status_code=_status_for_error(error), content=api_error_response(error))

    @app.get("/api/health")
    def health() -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        return HealthResponse(status="ok", workspace=str(workspace.root)).to_dict()

    @app.get("/api/doctor")
    def doctor() -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        checks = [
            DoctorCheckResponse(name=name, ok=ok, detail=detail).to_dict()
            for name, ok, detail in doctor_checks(workspace)
        ]
        return {"checks": checks}

    @app.get("/api/sessions")
    def sessions() -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        return {"sessions": RuntimeService(workspace).list_sessions()}

    @app.post("/api/sessions")
    def create_session(payload: dict[str, object]) -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        task = str(payload.get("task") or "").strip()
        if not task:
            raise ApiError(
                code="invalid_transition",
                message="Session task is required",
                retryable=False,
            )
        provider = str(payload.get("provider") or "mock")
        project = payload.get("project")
        session_id = payload.get("session_id")
        return RuntimeService(workspace).create_session(
            task=task,
            provider=provider,
            project=str(project) if project else None,
            session_id=str(session_id) if session_id else None,
        )

    @app.get("/api/sessions/{session_id}/state")
    def session_state(session_id: str) -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        return RuntimeService(workspace).get_state(session_id)

    @app.get("/api/sessions/{session_id}/trace")
    def session_trace(session_id: str) -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        return {"trace": RuntimeService(workspace).get_trace(session_id)}

    @app.get("/api/sessions/{session_id}/audit")
    def session_audit(session_id: str) -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        return {"audit": RuntimeService(workspace).get_audit(session_id)}

    @app.get("/api/sessions/{session_id}/artifact/{agent}")
    def session_artifact(session_id: str, agent: str) -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        return {"artifact": RuntimeService(workspace).get_artifact(session_id, agent)}

    @app.post("/api/sessions/{session_id}/run-one-step")
    def run_one_step(session_id: str) -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        return RuntimeService(workspace).run_one_step(session_id)

    @app.post("/api/sessions/{session_id}/continue")
    def continue_session(session_id: str) -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        return RuntimeService(workspace).continue_session(session_id)

    @app.post("/api/sessions/{session_id}/retry")
    def retry_session(session_id: str) -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        return RuntimeService(workspace).retry_session(session_id)

    @app.get("/api/workspace/tree")
    def workspace_tree() -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        return {"tree": [node.to_dict() for node in WorkspaceService(workspace).tree()]}

    @app.get("/api/file")
    def read_file(path: str) -> dict[str, object]:
        workspace = _require_workspace(workspace_root)
        return {
            "path": path,
            "content": WorkspaceService(workspace).read_file(path),
        }

    return app


def _allowed_origins_from_env() -> list[str]:
    raw = os.environ.get("AT_ALLOWED_ORIGINS", "")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or list(_DEFAULT_ALLOWED_ORIGINS)


def _require_workspace(root: Path) -> ATWorkspace:
    try:
        return ATWorkspace.require(root)
    except ConfigError as exc:
        raise ApiError(
            code="runtime_not_initialized",
            message=str(exc),
            retryable=False,
        ) from exc


def _status_for_error(error: ApiError) -> int:
    if error.code == "runtime_not_initialized":
        return 503
    if error.code == "session_not_found":
        return 404
    if error.code == "file_not_allowed":
        return 403
    if error.code == "invalid_transition":
        return 400
    return 500

# AT Flow V1.5 Web Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a front/back separated AT Flow web console that runs locally with a React/Vite frontend on port `3000` and a FastAPI backend on port `8000`.

**Architecture:** The existing AT runtime remains the source of truth. The FastAPI backend is a controlled adapter around AT runtime state and commands. The React frontend renders sessions, workspace files, documents, state machine, trace, audit, artifacts, errors, and safe runtime controls.

**Tech Stack:** Python `>=3.10`, FastAPI, SQLite, React, Vite, TypeScript, local backend port `8000`, local frontend port `3000`.

## Global Constraints

- Execute one task node at a time.
- Before each task node, update the current plan status in `agent.md`.
- Every task node must include targeted unit tests.
- A task node is not complete until its targeted tests pass.
- Do not start the next task node until the current task node's targeted tests pass.
- After frontend feature completion, run integration tests and sandbox tests.
- The `.at/` runtime state remains the source of truth.
- SQLite stores web console metadata only.
- No browser-based file editing in V1.5.
- No file deletion, upload, or bulk filesystem operations in V1.5.
- No API key management UI in V1.5.
- No WebSocket streaming in V1.5.
- No arbitrary shell execution endpoint.
- Do not expose secrets, environment variables, or arbitrary absolute paths.
- Backend must reject absolute browser paths and path traversal.
- Implementation commits require explicit user approval.

---

## Planned File Structure

Backend package:

- Create `src/at_flow/web/__init__.py`: web package marker.
- Create `src/at_flow/web/errors.py`: typed API error model and FastAPI exception mapping.
- Create `src/at_flow/web/schemas.py`: response DTOs shared by backend endpoints.
- Create `src/at_flow/web/workspace_service.py`: safe workspace tree and read-only file access.
- Create `src/at_flow/web/runtime_service.py`: session, trace, audit, artifact, and command adapter around AT runtime.
- Create `src/at_flow/web/db.py`: SQLite connection and metadata tables.
- Create `src/at_flow/web/app.py`: FastAPI app factory and route registration.
- Create `src/at_flow/web/__main__.py`: local backend entry point.

Backend tests:

- Create `tests/test_web_errors.py`.
- Create `tests/test_web_workspace_service.py`.
- Create `tests/test_web_runtime_service.py`.
- Create `tests/test_web_api.py`.
- Create `tests/test_web_db.py`.

Frontend app:

- Create `web/package.json`.
- Create `web/index.html`.
- Create `web/vite.config.ts`.
- Create `web/tsconfig.json`.
- Create `web/src/main.tsx`.
- Create `web/src/App.tsx`.
- Create `web/src/api/client.ts`.
- Create `web/src/api/types.ts`.
- Create `web/src/components/AppShell.tsx`.
- Create `web/src/components/TopBar.tsx`.
- Create `web/src/components/SessionList.tsx`.
- Create `web/src/components/WorkspaceTree.tsx`.
- Create `web/src/components/DocumentViewer.tsx`.
- Create `web/src/components/StateMachine.tsx`.
- Create `web/src/components/RuntimeEvidence.tsx`.
- Create `web/src/components/RunControls.tsx`.
- Create `web/src/styles.css`.

Frontend tests:

- Create `web/src/api/client.test.ts`.
- Create `web/src/components/AppShell.test.tsx`.
- Create `web/src/components/WorkspaceTree.test.tsx`.
- Create `web/src/components/DocumentViewer.test.tsx`.
- Create `web/src/components/StateMachine.test.tsx`.
- Create `web/src/components/RunControls.test.tsx`.

Docs:

- Modify `pyproject.toml`: add backend web dependencies after explicit approval to install/use them.
- Modify `README.md`: add local web console usage after implementation works.
- Modify `agent.md`: track V1.5 node status.

## Task 1: Web Error and Schema Contracts

**Files:**
- Create: `src/at_flow/web/__init__.py`
- Create: `src/at_flow/web/errors.py`
- Create: `src/at_flow/web/schemas.py`
- Test: `tests/test_web_errors.py`

**Interfaces:**
- Produces: `ApiErrorCode`, `ApiError`, `api_error_response(error: ApiError) -> dict[str, object]`
- Produces: `HealthResponse`, `DoctorCheckResponse`, `CommandResultResponse`, `FileNodeResponse`
- Consumes: no web modules from earlier tasks

- [ ] **Step 1: Update `agent.md` current node**

Set current V1.5 node to:

```text
Task 1: Web Error and Schema Contracts
```

- [ ] **Step 2: Write failing unit tests**

Create `tests/test_web_errors.py`:

```python
from at_flow.web.errors import ApiError, api_error_response


def test_api_error_response_contains_code_message_retryable_and_details():
    error = ApiError(
        code="session_not_found",
        message="Unknown session: abc",
        retryable=False,
        details={"session_id": "abc"},
    )

    assert api_error_response(error) == {
        "error": {
            "code": "session_not_found",
            "message": "Unknown session: abc",
            "retryable": False,
            "details": {"session_id": "abc"},
        }
    }


def test_api_error_response_omits_none_details():
    error = ApiError(
        code="internal_error",
        message="Unexpected failure",
        retryable=False,
    )

    assert api_error_response(error) == {
        "error": {
            "code": "internal_error",
            "message": "Unexpected failure",
            "retryable": False,
        }
    }
```

- [ ] **Step 3: Run failing test**

Run:

```powershell
python -m unittest tests.test_web_errors -v
```

Expected: fail because `at_flow.web.errors` does not exist.

- [ ] **Step 4: Implement minimal contracts**

Create `src/at_flow/web/errors.py`:

```python
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
```

Create `src/at_flow/web/schemas.py` with dataclasses only. Do not add FastAPI or Pydantic in this task.

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m unittest tests.test_web_errors -v
```

Expected: pass.

- [ ] **Step 6: Run current runtime regression tests**

Run:

```powershell
python -m unittest discover -s tests
```

Expected: pass.

- [ ] **Step 7: Stop for node review**

Report changed files, targeted test result, full regression result, and risks. Do not start Task 2 until Task 1 passes.

## Task 2: Safe Workspace Tree and File Reader

**Files:**
- Create: `src/at_flow/web/workspace_service.py`
- Test: `tests/test_web_workspace_service.py`

**Interfaces:**
- Consumes: `FileNodeResponse` from `src/at_flow/web/schemas.py`
- Produces: `WorkspaceService(workspace: ATWorkspace)`
- Produces: `WorkspaceService.tree() -> list[FileNodeResponse]`
- Produces: `WorkspaceService.read_file(relative_path: str) -> str`

- [ ] **Step 1: Update `agent.md` current node**

Set current V1.5 node to:

```text
Task 2: Safe Workspace Tree and File Reader
```

- [ ] **Step 2: Write failing unit tests**

Create `tests/test_web_workspace_service.py` with tests for:

```python
def test_workspace_tree_exposes_agent_documents(tmp_path):
    workspace = ATWorkspace.init(tmp_path)
    tree = WorkspaceService(workspace).tree()
    assert any(node.path == "agents/main/agent.md" for node in flatten(tree))


def test_read_file_allows_tree_relative_path(tmp_path):
    workspace = ATWorkspace.init(tmp_path)
    text = WorkspaceService(workspace).read_file("agents/main/agent.md")
    assert "main" in text.lower()


def test_read_file_rejects_path_traversal(tmp_path):
    workspace = ATWorkspace.init(tmp_path)
    with pytest.raises(ApiError) as exc:
        WorkspaceService(workspace).read_file("../at.config.json")
    assert exc.value.code == "file_not_allowed"


def test_read_file_rejects_absolute_path(tmp_path):
    workspace = ATWorkspace.init(tmp_path)
    absolute = str(workspace.root / "at.config.json")
    with pytest.raises(ApiError) as exc:
        WorkspaceService(workspace).read_file(absolute)
    assert exc.value.code == "file_not_allowed"
```

If the project keeps `unittest` only, use `self.assertRaises` instead of `pytest.raises`.

- [ ] **Step 3: Run failing tests**

Run:

```powershell
python -m unittest tests.test_web_workspace_service -v
```

Expected: fail because `WorkspaceService` does not exist.

- [ ] **Step 4: Implement service**

Implement allowlisted roots:

```text
agents/
shared/
sessions/
```

Reject:

```text
absolute paths
paths containing ..
paths resolving outside workspace root
directories
```

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m unittest tests.test_web_workspace_service -v
```

Expected: pass.

- [ ] **Step 6: Run current runtime regression tests**

Run:

```powershell
python -m unittest discover -s tests
```

Expected: pass.

- [ ] **Step 7: Stop for node review**

Do not start Task 3 until Task 2 passes.

## Task 3: Runtime Read Service

**Files:**
- Create: `src/at_flow/web/runtime_service.py`
- Test: `tests/test_web_runtime_service.py`

**Interfaces:**
- Produces: `RuntimeService(workspace: ATWorkspace)`
- Produces: `RuntimeService.list_sessions() -> list[dict[str, object]]`
- Produces: `RuntimeService.get_state(session_id: str) -> dict[str, object]`
- Produces: `RuntimeService.get_trace(session_id: str) -> list[dict[str, object]]`
- Produces: `RuntimeService.get_audit(session_id: str) -> list[dict[str, object]]`
- Produces: `RuntimeService.get_artifact(session_id: str, agent: str) -> str`
- Consumes: `session_trace_summary`, `session_audit_summary`, `session_artifact_text`

- [ ] **Step 1: Update `agent.md` current node**

Set current V1.5 node to:

```text
Task 3: Runtime Read Service
```

- [ ] **Step 2: Write failing unit tests**

Create tests for:

```python
def test_list_sessions_returns_empty_list_for_initialized_workspace(tmp_path):
    workspace = ATWorkspace.init(tmp_path)
    assert RuntimeService(workspace).list_sessions() == []


def test_get_state_returns_session_dict(tmp_path):
    workspace = ATWorkspace.init(tmp_path)
    session = SessionState.new(
        task="demo",
        project_path=workspace.projects_root / "default",
        provider="mock",
        pipeline=["main", "analysis", "code", "test"],
        session_id="demo-session",
    )
    workspace.create_session(session)
    state = RuntimeService(workspace).get_state("demo-session")
    assert state["id"] == "demo-session"
    assert [step["agent"] for step in state["steps"]] == ["main", "analysis", "code", "test"]


def test_get_state_maps_unknown_session_to_api_error(tmp_path):
    workspace = ATWorkspace.init(tmp_path)
    with self.assertRaises(ApiError) as raised:
        RuntimeService(workspace).get_state("missing")
    assert raised.exception.code == "session_not_found"
```

- [ ] **Step 3: Run failing tests**

Run:

```powershell
python -m unittest tests.test_web_runtime_service -v
```

Expected: fail because `RuntimeService` does not exist.

- [ ] **Step 4: Implement service**

Map `WorkspaceError` for unknown sessions to:

```python
ApiError(code="session_not_found", message=str(exc), retryable=False)
```

Return runtime dictionaries from `SessionState.to_dict()` rather than duplicating schema conversion.

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m unittest tests.test_web_runtime_service -v
```

Expected: pass.

- [ ] **Step 6: Run full regression**

Run:

```powershell
python -m unittest discover -s tests
```

Expected: pass.

- [ ] **Step 7: Stop for node review**

Do not start Task 4 until Task 3 passes.

## Task 4: FastAPI Read-Only Backend

**Files:**
- Modify: `pyproject.toml`
- Create: `src/at_flow/web/app.py`
- Create: `src/at_flow/web/__main__.py`
- Test: `tests/test_web_api.py`

**Interfaces:**
- Produces: `create_app(root: Path | str = ".") -> FastAPI`
- Produces endpoints: `GET /api/health`, `GET /api/doctor`, `GET /api/sessions`, `GET /api/sessions/{session_id}/state`, `GET /api/workspace/tree`, `GET /api/file`
- Consumes: `WorkspaceService`, `RuntimeService`, `doctor_checks`

- [ ] **Step 1: Confirm dependency installation**

FastAPI and its test client require new dependencies. Before executing this task, ask for approval to install/use:

```text
fastapi
uvicorn
httpx
```

- [ ] **Step 2: Update `agent.md` current node**

Set current V1.5 node to:

```text
Task 4: FastAPI Read-Only Backend
```

- [ ] **Step 3: Write failing API tests**

Create tests that call:

```python
client = TestClient(create_app(tmp_path))
assert client.get("/api/health").json()["status"] == "ok"
assert client.get("/api/sessions").json() == {"sessions": []}
assert client.get("/api/file", params={"path": "../at.config.json"}).status_code == 403
```

- [ ] **Step 4: Run failing tests**

Run:

```powershell
python -m unittest tests.test_web_api -v
```

Expected: fail until FastAPI app exists.

- [ ] **Step 5: Implement read-only app**

Create app factory and exception handler for `ApiError`. Use `ATWorkspace.require(root)` for normal operation. If workspace is missing, return `runtime_not_initialized`.

- [ ] **Step 6: Run targeted tests**

Run:

```powershell
python -m unittest tests.test_web_api -v
```

Expected: pass.

- [ ] **Step 7: Run backend server smoke command**

Run:

```powershell
python -m at_flow.web --root .
```

Expected: backend starts on port `8000`. Stop it after confirming startup.

- [ ] **Step 8: Run full regression**

Run:

```powershell
python -m unittest discover -s tests
```

Expected: pass.

- [ ] **Step 9: Stop for node review**

Do not start Task 5 until Task 4 passes.

## Task 5: SQLite Metadata and Runtime Command Endpoints

**Files:**
- Create: `src/at_flow/web/db.py`
- Modify: `src/at_flow/web/runtime_service.py`
- Modify: `src/at_flow/web/app.py`
- Test: `tests/test_web_db.py`
- Test: `tests/test_web_api.py`

**Interfaces:**
- Produces: `WebConsoleDb(path: Path)`
- Produces: `WebConsoleDb.record_request(method: str, path: str, status_code: int) -> None`
- Produces command endpoints: `POST /api/sessions`, `POST /api/sessions/{session_id}/run-one-step`, `POST /api/sessions/{session_id}/continue`, `POST /api/sessions/{session_id}/retry`

- [ ] **Step 1: Update `agent.md` current node**

Set current V1.5 node to:

```text
Task 5: SQLite Metadata and Runtime Command Endpoints
```

- [ ] **Step 2: Write failing DB tests**

Test that request history is inserted into SQLite and can be read back.

- [ ] **Step 3: Write failing command endpoint tests**

Test:

```python
response = client.post("/api/sessions", json={"task": "demo", "provider": "mock"})
assert response.status_code == 200
session_id = response.json()["session"]["id"]
assert client.post(f"/api/sessions/{session_id}/run-one-step").status_code == 200
```

- [ ] **Step 4: Implement SQLite metadata**

Create `.at/web/console.sqlite3` by default. Do not store secrets or runtime state copies.

- [ ] **Step 5: Implement command endpoints**

Use `ATWorkspace.create_session`, `Runner.run(..., one_step=True)`, `Runner.run(...)`, and `Runner.retry(...)`.

- [ ] **Step 6: Run targeted tests**

Run:

```powershell
python -m unittest tests.test_web_db tests.test_web_api -v
```

Expected: pass.

- [ ] **Step 7: Run full regression**

Run:

```powershell
python -m unittest discover -s tests
```

Expected: pass.

- [ ] **Step 8: Stop for node review**

Do not start Task 6 until Task 5 passes.

## Task 6: Frontend Scaffold and API Client

**Files:**
- Create: `web/package.json`
- Create: `web/index.html`
- Create: `web/vite.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/api/client.ts`
- Create: `web/src/api/types.ts`
- Test: `web/src/api/client.test.ts`

**Interfaces:**
- Produces: `AtApiClient`
- Produces: `getHealth()`, `getDoctor()`, `getSessions()`, `getWorkspaceTree()`, `getFile(path)`

- [ ] **Step 1: Confirm Node dependency installation**

Frontend implementation requires npm packages. Ask for approval before installing:

```text
react
react-dom
@vitejs/plugin-react
vite
typescript
vitest
@testing-library/react
@testing-library/jest-dom
jsdom
lucide-react
```

- [ ] **Step 2: Update `agent.md` current node**

Set current V1.5 node to:

```text
Task 6: Frontend Scaffold and API Client
```

- [ ] **Step 3: Write failing API client tests**

Test that `AtApiClient.getHealth()` calls `/api/health` and returns parsed JSON using a mocked `fetch`.

- [ ] **Step 4: Run failing tests**

Run:

```powershell
cd web
npm test -- --run src/api/client.test.ts
```

Expected: fail until client exists.

- [ ] **Step 5: Implement frontend scaffold and API client**

Use `VITE_AT_API_BASE_URL`, defaulting to `http://localhost:8000`.

- [ ] **Step 6: Run targeted tests**

Run:

```powershell
cd web
npm test -- --run src/api/client.test.ts
```

Expected: pass.

- [ ] **Step 7: Stop for node review**

Do not start Task 7 until Task 6 passes.

## Task 7: Console Layout, Workspace Tree, and Document Viewer

**Files:**
- Create: `web/src/components/AppShell.tsx`
- Create: `web/src/components/TopBar.tsx`
- Create: `web/src/components/SessionList.tsx`
- Create: `web/src/components/WorkspaceTree.tsx`
- Create: `web/src/components/DocumentViewer.tsx`
- Create: `web/src/styles.css`
- Modify: `web/src/App.tsx`
- Test: `web/src/components/AppShell.test.tsx`
- Test: `web/src/components/WorkspaceTree.test.tsx`
- Test: `web/src/components/DocumentViewer.test.tsx`

**Interfaces:**
- Consumes: `AtApiClient`
- Produces: first usable `/runtime` console shell

- [ ] **Step 1: Update `agent.md` current node**

Set current V1.5 node to:

```text
Task 7: Console Layout, Workspace Tree, and Document Viewer
```

- [ ] **Step 2: Write failing component tests**

Test:

```text
AppShell renders three regions: Sessions, Document Viewer, Runtime Inspector.
WorkspaceTree expands a node and calls onSelect(path).
DocumentViewer renders markdown/plain/json text without editing controls.
```

- [ ] **Step 3: Run failing tests**

Run:

```powershell
cd web
npm test -- --run src/components/AppShell.test.tsx src/components/WorkspaceTree.test.tsx src/components/DocumentViewer.test.tsx
```

Expected: fail until components exist.

- [ ] **Step 4: Implement components**

Keep layout dense and tool-like. Do not create a landing page. Use fixed panel constraints and responsive stacking for mobile width.

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
cd web
npm test -- --run src/components/AppShell.test.tsx src/components/WorkspaceTree.test.tsx src/components/DocumentViewer.test.tsx
```

Expected: pass.

- [ ] **Step 6: Stop for node review**

Do not start Task 8 until Task 7 passes.

## Task 8: State Machine, Evidence, and Runtime Controls

**Files:**
- Create: `web/src/components/StateMachine.tsx`
- Create: `web/src/components/RuntimeEvidence.tsx`
- Create: `web/src/components/RunControls.tsx`
- Modify: `web/src/components/AppShell.tsx`
- Test: `web/src/components/StateMachine.test.tsx`
- Test: `web/src/components/RunControls.test.tsx`

**Interfaces:**
- Consumes: `AtApiClient` command methods
- Produces: per-agent state display and controlled runtime actions

- [ ] **Step 1: Update `agent.md` current node**

Set current V1.5 node to:

```text
Task 8: State Machine, Evidence, and Runtime Controls
```

- [ ] **Step 2: Write failing component tests**

Test:

```text
StateMachine renders main, analysis, code, test.
StateMachine distinguishes session status from step status.
RunControls calls create session, run one step, continue, retry, and doctor refresh callbacks.
RuntimeEvidence renders trace, audit, artifact, and typed error data.
```

- [ ] **Step 3: Run failing tests**

Run:

```powershell
cd web
npm test -- --run src/components/StateMachine.test.tsx src/components/RunControls.test.tsx
```

Expected: fail until components exist.

- [ ] **Step 4: Implement components and polling**

Implement polling intervals:

```text
session state: 1000ms while active
trace: 2000ms while active
audit: 3000ms while active
doctor: manual plus initial load
```

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
cd web
npm test -- --run src/components/StateMachine.test.tsx src/components/RunControls.test.tsx
```

Expected: pass.

- [ ] **Step 6: Stop for node review**

Do not start Task 9 until Task 8 passes.

## Task 9: Integration Test, Browser Verification, Sandbox Test, and Docs

**Files:**
- Modify: `README.md`
- Optional create: `scripts/dev-web.ps1`
- Optional create: `tests/test_web_sandbox.py`

**Interfaces:**
- Consumes: completed backend and frontend
- Produces: verified local demo path

- [ ] **Step 1: Update `agent.md` current node**

Set current V1.5 node to:

```text
Task 9: Integration Test, Browser Verification, Sandbox Test, and Docs
```

- [ ] **Step 2: Run backend unit tests**

Run:

```powershell
python -m unittest discover -s tests
```

Expected: pass.

- [ ] **Step 3: Run frontend unit tests**

Run:

```powershell
cd web
npm test -- --run
```

Expected: pass.

- [ ] **Step 4: Start backend**

Run:

```powershell
python -m at_flow.web --root . --host 127.0.0.1 --port 8000
```

Expected: backend listens on `http://127.0.0.1:8000`.

- [ ] **Step 5: Start frontend**

Run:

```powershell
cd web
npm run dev -- --host 127.0.0.1 --port 3000
```

Expected: frontend listens on `http://127.0.0.1:3000/runtime`.

- [ ] **Step 6: Run integration smoke check**

Verify:

```text
GET http://127.0.0.1:8000/api/health returns status ok.
Frontend loads /runtime.
Workspace tree loads from backend.
Session state loads from backend.
Create session works.
Run one step works with mock provider.
```

- [ ] **Step 7: Run sandbox checks**

Verify:

```text
/api/file?path=../at.config.json is rejected.
/api/file?path=<absolute-path> is rejected.
No write/delete/upload endpoint exists.
No arbitrary command endpoint exists.
SQLite contains console metadata only.
```

- [ ] **Step 8: Browser screenshots**

Capture:

```text
desktop viewport
mobile-width viewport
```

Check:

```text
no overlapping text
no unusable controls
state machine visible
document tree visible
runtime inspector visible
```

- [ ] **Step 9: Update README**

Document:

```text
backend startup
frontend startup
localhost URLs
known V1.5 limitations
deployment notes for future cloud server
```

- [ ] **Step 10: Final verification report**

Report:

```text
changed files
backend tests
frontend tests
integration smoke result
sandbox result
browser verification result
known risks
```


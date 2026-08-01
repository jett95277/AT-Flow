# AT Flow V1.5 Web Console Design

Date: 2026-08-01

## Status

Approved for design documentation. Not approved for implementation yet.

## Goal

Build a usable web console for AT Flow that can be demonstrated to interviewers and later deployed to a personal cloud server. The console must show AT's multi-agent runtime clearly, expose the state machine in real time, display each agent's documents through a VSCode-like file explorer, and provide controlled runtime actions through a FastAPI backend.

V1.5 is not a new agent framework. It is a front/back separated control surface around the existing AT runtime.

## Target User

The primary audience is an interviewer or reviewer evaluating AT Flow as an engineering project.

The interface should make these points visible without requiring the reviewer to read source code first:

- AT has strict agent responsibility boundaries.
- Runtime state is explicit and observable.
- Artifacts, trace logs, audit logs, and errors are inspectable.
- The system can be operated through a real UI, not only a CLI.

## Non-Goals

V1.5 will not include:

- Browser-based file editing.
- File deletion, upload, or bulk filesystem operations.
- API key management UI.
- User account system.
- Production multi-tenant isolation.
- WebSocket streaming.
- LangGraph, CrewAI, or other orchestration framework integration.
- Replacing the existing `.at/` runtime state files with database state.

These are intentionally deferred to avoid expanding scope before the console is usable and reliable.

## Architecture

```text
Browser UI :3000
  |
  | HTTP polling / commands
  v
FastAPI Backend :8000
  |
  | controlled adapter calls
  v
AT Runtime
  |
  | filesystem state
  v
Project workspace + .at/

SQLite
  |
  v
web console metadata only
```

The existing AT runtime remains the source of truth for sessions, artifacts, agent packages, traces, and audit records. The backend reads and invokes AT through stable Python interfaces where available. If a required runtime operation is only available through CLI today, the backend may wrap it explicitly, but that wrapper must be marked as temporary and tested.

SQLite is used only for web-console metadata such as UI job records, recent session selection, and backend request history. It must not become the authority for runtime state.

## Technology Choices

Frontend:

- React
- Vite
- TypeScript
- Local development port: `3000`

Backend:

- FastAPI
- SQLite
- Local development port: `8000`

Rationale:

- React/Vite gives a fast demo-quality UI without heavy framework lock-in.
- FastAPI fits the current Python runtime and avoids cross-language orchestration for V1.5.
- SQLite is enough for local demo metadata and avoids external infrastructure.

## Frontend Layout

The console uses one main application screen at `/runtime`. There is no landing page.

```text
+-----------------------------------------------------------------------------+
| AT Flow Console                                      Provider  Doctor  Run   |
+-----------------------+--------------------------------+--------------------+
| Sessions              | Document Viewer                | Runtime Inspector  |
| - active session      | - selected agent.md            | - state machine    |
| - previous sessions   | - memory / skill docs          | - agent status     |
|                       | - artifacts                    | - trace            |
| Workspace             |                                | - audit            |
| v agents              |                                | - errors           |
|   v main              |                                | - controls         |
|     agent.md          |                                |                    |
|   v analysis          |                                |                    |
|   v code              |                                |                    |
|   v test              |                                |                    |
| v shared              |                                |                    |
| v sessions            |                                |                    |
+-----------------------+--------------------------------+--------------------+
```

The left panel provides navigation. The center panel shows selected files or artifacts. The right panel shows runtime state and actions.

This layout is chosen because AT is an engineering tool, not a marketing product. The first screen must show the actual system: sessions, files, state, artifacts, and controls.

## Core UI Components

### AppShell

Owns the page structure, split panels, current selected session, selected file, and API connectivity state.

### TopBar

Shows:

- Project name.
- Backend health.
- Provider mode.
- Doctor status.
- Primary run action.

### SessionList

Shows current and previous sessions. A session entry should expose:

- Session ID.
- Current phase.
- Current step.
- Status.
- Last update time.

### WorkspaceTree

Shows a VSCode-like collapsible tree for AT-controlled files:

- Agent directories.
- `agent.md` files.
- Shared memory and skill documents.
- Session artifacts.
- Trace and audit files when available.

The tree must only expose safe, backend-authorized relative paths. The browser never receives arbitrary absolute filesystem access.

### DocumentViewer

Shows the selected file or artifact as read-only content. Supported display modes for V1.5:

- Markdown text.
- Plain text.
- JSON formatted text.

V1.5 does not support editing.

### StateMachine

Shows the current AT session flow and each agent's status.

Required states:

- `idle`
- `queued`
- `running`
- `succeeded`
- `failed`
- `interrupted`
- `retryable`
- `blocked`

Required per-agent visibility:

- `main`
- `analysis`
- `code`
- `test`

The state machine must distinguish session-level state from agent-level step state. This is important because one session can be alive while one agent step has failed or is retryable.

### RuntimeEvidence

Shows trace, audit, artifact validation results, and error details for the selected session.

This is a first-class part of the UI. Multi-agent systems are not maintainable if failures are hidden behind a generic failed label.

### RunControls

Allowed V1.5 actions:

- Create session.
- Run one step.
- Continue session.
- Retry failed or interrupted step.
- Refresh doctor status.

Disallowed V1.5 actions:

- Delete session.
- Edit runtime files.
- Upload files.
- Change provider keys.
- Execute arbitrary shell commands.

## Backend API

Base URL for local development:

```text
http://localhost:8000
```

Planned endpoints:

```text
GET  /api/health
GET  /api/doctor

GET  /api/sessions
POST /api/sessions
GET  /api/sessions/{session_id}/state
POST /api/sessions/{session_id}/run-one-step
POST /api/sessions/{session_id}/continue
POST /api/sessions/{session_id}/retry

GET  /api/sessions/{session_id}/trace
GET  /api/sessions/{session_id}/audit
GET  /api/sessions/{session_id}/artifact/{agent}

GET  /api/workspace/tree
GET  /api/file?path=<safe-relative-path>
```

API design rules:

- Every command endpoint returns a structured result.
- Every failure returns a typed error code, message, and retryability flag.
- Backend responses must not expose secrets.
- Backend responses must not expose arbitrary absolute paths.
- Runtime mutation must go through explicit command endpoints only.

## Polling Model

V1.5 uses polling instead of WebSocket streaming.

Intervals:

- Session state: every 1 second while a session is active.
- Trace: every 2 seconds while a session is active.
- Audit: every 3 seconds while a session is active.
- Doctor: manual refresh, plus initial load.

Rationale:

- Polling is enough for a local/demo console.
- It is simpler to test.
- It avoids adding connection recovery complexity before the runtime console is stable.

WebSocket or server-sent events can be considered in a later version after the API contract is stable.

## Data Ownership

Runtime source of truth:

- `.at/sessions`
- `.at/shared`
- agent package files
- trace logs
- audit logs
- artifact outputs

SQLite source of truth:

- web console request history
- UI job IDs if backend operations become asynchronous
- recent selected session
- non-sensitive display preferences

SQLite must not be used to repair or override AT runtime state.

## Safety Boundaries

The backend is a controlled adapter, not a general remote shell.

V1.5 safety rules:

- Only read files under approved AT workspace paths.
- Only allow safe relative file paths from `/api/workspace/tree`.
- Reject path traversal such as `..`.
- Reject absolute file paths from browser requests.
- Do not expose environment variables.
- Do not log API keys.
- Do not provide arbitrary command execution.
- Do not provide file write/delete endpoints.

Provider configuration stays outside the browser. The user may later connect GPT or Codex APIs through environment variables or backend configuration.

## Error Handling

Every backend error should map to one of these categories:

- `runtime_not_initialized`
- `session_not_found`
- `invalid_transition`
- `step_failed`
- `step_interrupted`
- `artifact_invalid`
- `file_not_allowed`
- `provider_unavailable`
- `internal_error`

Each error response should include:

- `code`
- `message`
- `retryable`
- `details` when safe to expose

The UI must show errors in the Runtime Inspector, not only as temporary toast messages.

## Testing Strategy

Backend tests:

- health endpoint
- doctor endpoint
- session listing with no sessions
- create session
- read session state
- invalid session ID
- safe file read
- rejected absolute path
- rejected path traversal
- failed runtime command response shape

Frontend tests:

- app renders with backend health response
- workspace tree expands and selects a file
- document viewer displays Markdown/plain text/JSON
- state machine renders session and per-agent states
- run controls call correct API endpoints
- error panel renders typed backend errors

Integration smoke test:

- Start backend on `8000`.
- Start frontend on `3000`.
- Load `/runtime`.
- Confirm UI can call `/api/health`.
- Confirm workspace tree and session state can load from backend.

Browser verification:

- Desktop viewport screenshot.
- Mobile-width viewport screenshot.
- Check for text overflow, overlapping panels, and unusable controls.

## Development Phases

### Phase 1: Backend Adapter Skeleton

Create the FastAPI application, health endpoint, doctor endpoint, workspace path guard, and session read endpoints.

Success criteria:

- Backend runs locally on `8000`.
- API can inspect existing AT state without mutating it.
- Path safety tests pass.

### Phase 2: Frontend Console Skeleton

Create React/Vite/TypeScript frontend and static layout with live health connection.

Success criteria:

- Frontend runs locally on `3000`.
- UI connects to backend health endpoint.
- Main three-panel console layout is visible.

### Phase 3: Workspace and Document Viewer

Add workspace tree and read-only document viewer.

Success criteria:

- User can browse agent docs and shared docs.
- File access goes through backend-safe relative paths only.

### Phase 4: Runtime State Machine

Add session list, state endpoint integration, and per-agent state visualization.

Success criteria:

- Current session and agent states are visible.
- State updates through polling.

### Phase 5: Controlled Runtime Actions

Add create session, run one step, continue, retry, and refresh doctor actions.

Success criteria:

- UI can operate the minimal AT runtime through backend endpoints.
- Errors are visible and typed.

### Phase 6: Demo Hardening

Add trace/audit/artifact panels, screenshots, browser verification, and README updates.

Success criteria:

- Interviewer can understand AT from the UI.
- Local demo path is documented.
- Known limitations are explicit.

## Open Risks

- The current AT runtime was built as a CLI-first system. Some operations may need stable Python service interfaces to avoid wrapping CLI commands.
- Real-time behavior is polling-based in V1.5, so it is near-real-time, not streaming.
- Frontend deployment will need CORS and environment configuration when moving from localhost to the user's cloud server.
- Provider integration is intentionally deferred; the UI will prepare provider selection but not manage secrets.

## Acceptance Criteria

V1.5 is acceptable when:

- `localhost:3000/runtime` opens the console.
- The frontend successfully connects to the FastAPI backend.
- The UI displays AT sessions, workspace tree, selected documents, state machine, trace/audit/artifact evidence, and typed errors.
- Runtime actions work through controlled backend endpoints.
- Path traversal and absolute path reads are rejected.
- Minimal backend and frontend tests pass.
- Browser screenshots confirm the layout is usable on desktop and mobile-width viewports.

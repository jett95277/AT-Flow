# AT V1.9 Web Console UI Remediation Design

## Goal

Turn the current V1.9 Web Console from a readable prototype into a usable local
runtime console without changing AT's backend orchestration model.

## Approved Scope

This remediation owns six review findings:

1. Make sessions selectable and visibly active.
2. Replace the hard-coded demo task with explicit task input.
3. Separate new-session CodeAgent selection from active-session switching.
4. Enforce state-machine eligibility in controls before requests are sent.
5. Preserve typed API errors and clear stale errors after successful actions.
6. Remove the duplicate `shared/agents` tree entry and make the three-panel
   console scroll and respond correctly.

The deeper state-machine timeline, richer trace rendering, server path masking,
and visual polish remain separate follow-up work.

## Approaches Considered

### A. Incremental remediation in existing components (selected)

Keep `AppShell`, `SessionList`, `RunControls`, `CodeAgentPanel`, and
`WorkspaceService`. Add narrow props and state helpers, then fix layout CSS.
This preserves the current API and minimizes regression risk.

### B. Rewrite the console around a global state store

This could simplify polling and cross-panel state later, but it introduces a new
dependency and changes too much for a V1.9 repair.

### C. CSS-only presentation repair

This would improve the screenshot but leave the broken session, task, transition,
and error workflows unchanged. It does not meet the usability goal.

## Component Contracts

### SessionList

`SessionList` receives the active session id and an `onSelect` callback. Every
session is a real button with `aria-current` and an active visual state. Selecting
a session clears stale evidence before polling the selected session.

### RunControls

`RunControls` has two explicit groups:

- New session: task text, `Initial CodeAgent`, and create action.
- Active session: run one step, continue, retry, and refresh diagnostics.

The `Initial CodeAgent` configures only the next session. It does not mutate the
active session. Active-session switching remains exclusively in
`CodeAgentPanel`.

### State Eligibility

Controls derive eligibility from the current session:

- run one step: enabled when a queued step exists and no step is running
- continue: enabled when a queued step exists and no step is running
- retry: enabled only when a failed step is retryable and below `max_retries`
- switch CodeAgent: disabled while any step is `running` or `retrying`
- create session: enabled only when the task contains non-whitespace text

Requests also expose an in-flight flag so duplicate clicks are blocked.

### Error Contract

`AppShell` stores `ApiErrorInfo`, not a plain string. `AtApiError.code`,
`AtApiError.message`, and `AtApiError.retryable` reach `RuntimeEvidence`
unchanged. Unknown errors become `client_error` and non-retryable. A new user
action clears the previous error before issuing its request, and a successful
mutation leaves the console free of stale errors. Successful background polls
must not erase a command failure before the user can inspect it.

### Workspace Tree

The physical canonical package is `.at/agents`. The API renders it as the
top-level `agents` branch. The top-level `shared` branch contains shared
knowledge only and has no platform-owned nested Agent package. Session snapshots
remain under `.at/sessions/<id>/agents`.

### Layout

Desktop uses a viewport-height grid with independently scrollable left, middle,
and right panels. At `900px` and below the page returns to document scrolling.
CodeAgent summary and capability grids collapse to two columns and then one
column on narrow screens.

## Testing

- Component tests cover session selection, task validation, initial CodeAgent
  semantics, action eligibility, active-session switch locking, and typed errors.
- Backend tests cover the physical absence of platform-owned `shared/agents`
  while retaining top-level `agents`.
- Full frontend tests and production build run after all nodes.
- Full backend tests run because the workspace tree API contract changes.

## Constraints

- No new frontend state-management or UI dependencies.
- No Git branch, commit, or push operations in this development window.
- No silent provider fallback.
- No runtime directory or permission-boundary changes.

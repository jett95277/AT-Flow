# AT V1.9 Web Console UI Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the V1.9 Web Console usable for selecting sessions, submitting real tasks, executing valid state transitions, inspecting typed failures, and working in a stable responsive layout.

**Architecture:** Keep the existing three-panel React application and FastAPI workspace API. Add explicit component contracts for selection and eligibility, preserve backend error types in `AppShell`, filter one duplicate tree alias in `WorkspaceService`, and constrain scrolling in CSS.

**Tech Stack:** React 19, TypeScript 5.9, Vitest, Testing Library, FastAPI, Python unittest, Vite 7.

## Execution Status

```text
Status: complete
Backend tests: 128 passed
Frontend tests: 38 passed
Production build: passed
Live integration: frontend 200, backend healthy, duplicate shared/agents removed
Session snapshot display: sessions/*.md translated on demand with .zh.md cache (v1.8 fix cherry-picked as 9496d55)
Visual browser automation: not run because the in-app browser blocks localhost automation by policy
Git operations: not performed by explicit user instruction
```

## Global Constraints

- Do not create or switch Git branches, commit, or push in this window.
- Write each behavioral test first and confirm the expected failure.
- Run the targeted test after every production change.
- Keep `CodeAgentPanel` as the only active-session provider switch.
- Do not add dependencies or change runtime permission boundaries.
- Do not silently fallback between providers.

---

### Task 1: Selectable Sessions

**Files:**
- Create: `web/src/components/SessionList.test.tsx`
- Modify: `web/src/components/SessionList.tsx`
- Modify: `web/src/components/AppShell.tsx`
- Modify: `web/src/components/AppShell.test.tsx`

**Interfaces:**
- Consumes: `SessionState.id`, `SessionState.status`, `SessionState.current_stage`, `SessionState.updated_at`
- Produces: `SessionList({ sessions, activeSessionId, onSelect })`

- [x] **Step 1: Write a failing SessionList interaction test**

```tsx
render(<SessionList sessions={[session]} activeSessionId={null} onSelect={onSelect} />);
fireEvent.click(screen.getByRole("button", { name: /s1/ }));
expect(onSelect).toHaveBeenCalledWith(session);
```

- [x] **Step 2: Run the targeted test and confirm it fails because session entries are not buttons**

Run: `npm.cmd test -- --run src/components/SessionList.test.tsx`

- [x] **Step 3: Implement selectable and active session rows**

Use a button per session, expose phase/status/update time, and set
`aria-current={activeSessionId === session.id ? "true" : undefined}`.

- [x] **Step 4: Add an AppShell test proving a selected session becomes the active state source**

The fake client must return two sessions and assert that selecting the second
session triggers `getState`, `getTrace`, `getAudit`, and `getProviderStatus` for
that id.

- [x] **Step 5: Implement `selectSession(session)` in AppShell**

Clear `trace`, `audit`, `artifact`, and `providerStatus`, then set the active
session. Pass `activeSessionId` and `onSelect` into `SessionList`.

- [x] **Step 6: Run SessionList and AppShell tests**

Run: `npm.cmd test -- --run src/components/SessionList.test.tsx src/components/AppShell.test.tsx`

---

### Task 2: Real Task Input and Explicit Initial CodeAgent

**Files:**
- Modify: `web/src/components/RunControls.tsx`
- Modify: `web/src/components/RunControls.test.tsx`
- Modify: `web/src/components/AppShell.tsx`
- Modify: `web/src/components/AppShell.test.tsx`

**Interfaces:**
- Consumes: provider names from `ProviderCapability[]`
- Produces: `task`, `initialProvider`, `onTaskChange`, `onInitialProviderChange`, and `onCreateSession`

- [x] **Step 1: Write failing tests for task validation and initial CodeAgent labeling**

```tsx
expect(screen.getByLabelText("任务")).toBeInTheDocument();
expect(screen.getByLabelText("初始 CodeAgent")).toHaveValue("mock");
expect(screen.getByRole("button", { name: "创建会话" })).toBeDisabled();
```

After entering non-whitespace task text, the create button must become enabled.

- [x] **Step 2: Run RunControls tests and confirm the missing-input failure**

Run: `npm.cmd test -- --run src/components/RunControls.test.tsx`

- [x] **Step 3: Implement the new-session form inside RunControls**

Replace the ambiguous `Provider` label with `初始 CodeAgent`, add a task
textarea, and derive options from provider names supplied by AppShell.

- [x] **Step 4: Write an AppShell test for the POST payload**

Enter `实现真实任务`, choose `auto`, click create, and assert:

```ts
expect(client.createSession).toHaveBeenCalledWith({ task: "实现真实任务", provider: "auto" });
```

- [x] **Step 5: Replace the hard-coded task in AppShell**

Store `taskDraft` and `initialProvider` separately from active-session provider
state. Trim task text before calling `createSession` and clear it after success.

- [x] **Step 6: Run RunControls and AppShell tests**

Run: `npm.cmd test -- --run src/components/RunControls.test.tsx src/components/AppShell.test.tsx`

---

### Task 3: State-Aware Actions and Provider Locking

**Files:**
- Modify: `web/src/components/RunControls.tsx`
- Modify: `web/src/components/RunControls.test.tsx`
- Modify: `web/src/components/CodeAgentPanel.tsx`
- Modify: `web/src/components/CodeAgentPanel.test.tsx`
- Modify: `web/src/components/AppShell.tsx`

**Interfaces:**
- Consumes: complete `SessionState` and request-pending state
- Produces: deterministic disabled states for every mutation control

- [x] **Step 1: Write failing tests for action eligibility**

Cover queued, running, done, retryable failed, and exhausted failed sessions.
Only valid actions may be enabled.

- [x] **Step 2: Write a failing CodeAgentPanel test for running-session locking**

Render a session with a running step and assert `选择 CodeAgent` is disabled.

- [x] **Step 3: Run both targeted suites and confirm the expected failures**

Run: `npm.cmd test -- --run src/components/RunControls.test.tsx src/components/CodeAgentPanel.test.tsx`

- [x] **Step 4: Implement eligibility helpers and pending state**

Derive `hasRunnableStep`, `hasRunningStep`, and `hasRetryableFailure` from the
session. Disable all mutation controls while a command or provider update is in
flight.

- [x] **Step 5: Run the targeted suites**

Run: `npm.cmd test -- --run src/components/RunControls.test.tsx src/components/CodeAgentPanel.test.tsx`

---

### Task 4: Preserve Typed Errors and Clear Stale Failures

**Files:**
- Modify: `web/src/components/AppShell.tsx`
- Modify: `web/src/components/AppShell.test.tsx`
- Modify: `web/src/components/TopBar.tsx`

**Interfaces:**
- Consumes: `AtApiError` from `web/src/api/client.ts`
- Produces: `ApiErrorInfo | null` shared by TopBar and RuntimeEvidence

- [x] **Step 1: Write a failing AppShell test for typed API errors**

Reject a command with `new AtApiError(409, { code: "invalid_transition", message: "blocked", retryable: true })` and assert the runtime inspector shows the original code, message, and retryability semantics.

- [x] **Step 2: Write a failing test proving a later successful action clears the error**

Trigger one rejected command, then a successful command, and assert the stale
error is removed.

- [x] **Step 3: Run AppShell tests and confirm both failures**

Run: `npm.cmd test -- --run src/components/AppShell.test.tsx`

- [x] **Step 4: Implement `toApiError` and explicit action lifecycle helpers**

Preserve `AtApiError` fields. Map unknown errors to
`{ code: "client_error", message, retryable: false }`. Clear errors before a
new explicit action and after a successful mutation; background polls must not
erase a command failure.

- [x] **Step 5: Run AppShell tests**

Run: `npm.cmd test -- --run src/components/AppShell.test.tsx`

---

### Task 5: Remove the Duplicate Shared Agent Tree

**Files:**
- Modify: `src/at_flow/web/workspace_service.py`
- Modify: `tests/test_web_workspace_service.py`
- Modify: `tests/test_web_api.py`

**Interfaces:**
- Keeps: top-level API path `agents/<agent>/...`
- Removes: duplicate display path `shared/agents/...`

- [x] **Step 1: Write a failing workspace-tree test**

```python
paths = flatten(WorkspaceService(workspace).tree())
self.assertIn("agents/main/agent.md", paths)
self.assertNotIn("shared/agents/main/agent.md", paths)
```

- [x] **Step 2: Run the targeted test and confirm `shared/agents` is present**

Run: `python -m unittest tests.test_web_workspace_service tests.test_web_api`

- [x] **Step 3: Filter only the root-level `agents` child under the shared alias**

Add an optional excluded-child set to `_node_for_path` and pass `{"agents"}`
only when rendering the `shared` top-level node. Do not change filesystem paths.

- [x] **Step 4: Run the targeted backend tests**

Run: `python -m unittest tests.test_web_workspace_service tests.test_web_api`

---

### Task 6: Stable Desktop Scrolling and Responsive CodeAgent Grids

**Files:**
- Modify: `web/src/styles.css`
- Test: `web/src/components/AppShell.test.tsx`

**Interfaces:**
- Desktop: viewport-height console with independently scrollable panels
- Mobile: document-flow single column without horizontal overflow

- [x] **Step 1: Add structural class assertions to AppShell tests**

Assert the left, middle, and runtime panels remain separate named regions or
landmarks so CSS can own scrolling without changing component semantics.

- [x] **Step 2: Update desktop layout CSS**

Use `height: calc(100vh - 48px)` and `overflow: hidden` on the grid, then
`overflow: auto` on each panel.

- [x] **Step 3: Update narrow layout CSS**

At `900px`, restore `height: auto` and visible overflow. Collapse CodeAgent
summary and catalog to two columns; at `560px`, collapse both to one column and
make the selector one column.

- [x] **Step 4: Run frontend tests and production build**

Run: `npm.cmd test -- --run`

Run: `npm.cmd run build`

---

### Task 7: Integration and Regression Verification

**Files:**
- Modify only if a failing verification exposes a defect covered by this plan.

**Interfaces:**
- Produces: verified V1.9 UI remediation with no Git mutation

- [x] **Step 1: Run the full backend suite**

Run: `python -m unittest discover tests`

- [x] **Step 2: Run the full frontend suite**

Run: `npm.cmd test -- --run`

- [x] **Step 3: Run the production build**

Run: `npm.cmd run build`

- [x] **Step 4: Check the workspace diff**

Run: `git diff --check`

Confirm there are no unrelated source changes, no silent fallback, and no Git
branch, commit, or push operation.

# AT Flow Development Agent Notes

## Current Development Rule

Before each development pass, update the current plan first.

Use this fixed workflow:

```text
1. Update the current development plan
2. State the single node being worked on
3. Write the failing test
4. Implement the minimum code
5. Run targeted tests
6. Run full verification
7. Report changes, verification, and risks
```

Do not expand scope during a node. If a new issue is found, record it and keep
the current node focused unless it blocks the work.

## MVP-2 Plan

```text
MVP-2: Reliable Minimal AT Runtime

[x] 1. Interrupted step recovery
[x] 2. Retry cleanup for stale artifacts
[x] 3. File-level context authorization
[x] 4. Artifact output validation
[x] 5. Trace/audit/doctor observability commands
```

Last completed node:

```text
5. Trace/audit/doctor observability commands
```

MVP-2 status:

```text
complete
```

## Completed Phase

```text
V1.5: Web Console
```

Current objective:

```text
Build a front/back separated AT Flow web console for local use and interview
demonstration. The console must connect to a FastAPI backend, display runtime
state, expose agent documents, and operate only through controlled backend
commands.
```

V1.5 status:

```text
complete
```

Current V1.5 plan:

```text
docs/superpowers/plans/2026-08-01-at-v1-5-web-console-implementation-plan.md
```

Current V1.5 node:

```text
none
```

Last completed V1.5 node:

```text
Task 9: Integration Test, Browser Verification, Sandbox Test, and Docs
```

## Current Phase

```text
V1.6: Codex Provider, Dual Entry, and Language Contract
```

Current objective:

```text
Keep AT Flow's two official usage modes while making mature Codex CLI capability
the preferred code-agent provider. Web Console mode and Codex Conversation mode
must both call the same AT runtime, provider adapters, state machine, artifacts,
trace, audit, and permission boundaries.
```

V1.6 status:

```text
planned
```

Current V1.6 plan:

```text
docs/superpowers/plans/2026-08-01-at-v1-6-codex-provider-and-dual-entry-plan.md
```

Current V1.6 node:

```text
Task 5: Web Console Provider Selection
```

V1.6 design decisions:

```text
1. AT has two official usage modes:
   - Codex Conversation Mode: user works inside Codex chat; AT state appears first.
   - Web Console Mode: user works in browser; backend calls the same AT runtime.
2. Codex is the preferred mature code-agent provider for code/test work.
3. GPT/OpenAI API may be added as a provider, but must not replace Codex by default.
4. agent.md restricts role and side effects, not Codex's engineering capability.
5. Hard boundaries belong to permissions.json, private workspaces, context.json,
   post-run audit, artifact validation, and state transition rules.
6. Language contract can keep frontend display in Chinese while runtime prompts
   and provider artifacts use English.
```

V1.5 execution rule:

```text
Each development node must update this file first, add or update targeted unit
tests, make those tests pass, and stop before the next node. After frontend
feature completion, run integration tests and sandbox tests before claiming the
web console is complete.
```

## Scope Freeze

Pause these until MVP-2 is complete:

```text
topic mode
timeline
SOP routing
persona overlay
ASCII polish
more agents
plugin packaging
```

The current goal is not to make AT feature-rich. The current goal is to make the
minimal runtime reliable when work is interrupted, retried, audited, and
verified.

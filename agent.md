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

## Current Phase

```text
MVP-3: Packaging Readiness
```

Current objective:

```text
Run acceptance tests, then decide the smallest safe packaging path for making
AT usable as a pluggable one-command platform.
```

MVP-3 status:

```text
minimal packaging entry complete
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

# AT Version Roadmap Design

## Purpose

This document defines the responsibility boundary for AT Flow V1.7, V1.8, and V1.9. Each version must have one primary mission, one verification target, and explicit non-goals. This keeps the project from mixing cloud deployment, Codex integration, and provider expansion into one unstable release.

## Version Boundary Principle

Each version must be isolated by capability ownership:

```text
V1.7 owns deployment.
V1.8 owns Codex capability.
V1.9 owns provider expansion.
```

A later version may depend on artifacts from earlier versions, but it must not smuggle its core feature into an earlier release.

## V1.7: Cloud Demo Release

### Mission

Make AT Flow accessible through a public HTTPS domain with the Web Console and FastAPI backend fully connected.

### Owns

- React production build.
- FastAPI production runtime.
- Nginx reverse proxy.
- HTTPS setup.
- systemd backend service.
- SQLite and `.at` runtime data persistence.
- Basic Auth or equivalent minimal public access protection.
- Reproducible deployment documentation for a fresh Ubuntu server.

### Default Provider

```text
mock
```

V1.7 must prove that the AT runtime, state machine, trace, audit, artifacts, file tree, and session flow work after deployment.

### Does Not Own

- Stable cloud execution of Codex CLI.
- Stable cloud execution of opencode.
- GPT/OpenAI API as a replacement for Codex.
- Full authentication system.
- Multi-user or multi-tenant runtime.

### Verification Gate

V1.7 is complete only when:

- `https://<domain>/` opens the Web Console.
- `https://<domain>/api/health` returns healthy backend state.
- A `mock` session can be created, stepped, continued, and inspected.
- Backend is managed by systemd and survives restart.
- Runtime data persists after backend restart.
- Port `8000` is not publicly exposed.

## V1.8: Codex Capability Release

### Mission

Make AT genuinely reuse mature Codex code-agent capability instead of merely calling a general GPT/OpenAI API.

### Owns

- Codex provider capability check.
- Codex CLI availability detection.
- Codex authentication and environment diagnostics.
- Non-interactive Codex execution contract.
- Clear failure artifacts when Codex cannot run.
- Web Console visibility for provider availability.
- Runtime trace events for Codex provider lifecycle.
- `code` and `test` agent path through Codex where available.

### OpenAI API Role

OpenAI/GPT API may be added as a supporting provider, but it must not replace Codex as the primary code-agent capability.

Allowed OpenAI API roles:

- translation
- summary
- lightweight analysis
- routing assistance
- language contract support

Not allowed as the V1.8 primary claim:

```text
Web input -> FastAPI -> GPT API -> pretend this is Codex-equivalent code-agent execution
```

### Does Not Own

- opencode integration.
- Provider marketplace.
- Multi-provider benchmarking.
- Full plugin packaging.

### Verification Gate

V1.8 is complete only when:

- AT can detect whether Codex is available.
- AT can report why Codex is unavailable.
- Codex execution failure is visible in session state, artifact, trace, and Web Console.
- At least one controlled Codex-backed agent step can run in a supported environment.
- `mock` remains available as the safe fallback for demos and tests.

## V1.9: Provider Extension Release

### Mission

Make opencode a first-class pluggable provider after the Codex provider contract is stable.

### Owns

- opencode provider capability check.
- opencode command contract.
- opencode execution diagnostics.
- Provider adapter contract cleanup.
- Provider comparison visibility in Web Console.
- Runtime support for selecting `mock`, `codex`, `opencode`, and OpenAI API providers without changing core state-machine logic.

### Does Not Own

- Reworking the V1.7 deployment topology.
- Replacing Codex provider semantics.
- Building a full plugin marketplace.
- Removing `mock` provider.

### Verification Gate

V1.9 is complete only when:

- opencode can be checked for availability.
- opencode unavailable state is explicit and observable.
- opencode provider execution follows the same context, artifact, trace, audit, and permission contract as Codex.
- Provider selection remains explicit: no silent fallback from one real provider to another.

## Cross-Version Invariants

These rules apply to all future versions:

- AT owns orchestration, state transitions, context construction, permission boundaries, artifact validation, trace, and audit.
- Providers execute bounded agent steps; providers do not own the AT state machine.
- No silent fallback between providers.
- `mock` remains the safe local and cloud demo provider.
- Runtime failures must be visible through state, trace, artifacts, and Web Console errors.
- Secrets must not be committed.
- Version scope must remain narrow enough to verify end to end.

## Recommended Execution Order

```text
1. Finish V1.7 cloud deployment.
2. Verify V1.7 on the public server with mock provider.
3. Start V1.8 Codex capability design and implementation.
4. Verify Codex provider behavior locally before relying on cloud execution.
5. Start V1.9 opencode extension only after Codex provider contract is stable.
```

## Current Decision

The project will not mix cloud deployment and real code-agent provider hardening in one release.

This is the accepted boundary:

```text
V1.7: deployable demo
V1.8: Codex capability
V1.9: opencode extension
```

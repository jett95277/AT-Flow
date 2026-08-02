# AT V1.9 CodeAgent Switch Design

## Goal

V1.9 makes CodeAgent selection explicit and visible in the Web Console. Users must be able to choose which code-agent provider AT uses for a session, see the current selected CodeAgent on the main page, and inspect provider availability before running work.

V1.9 extends provider usability. It does not replace AT's runtime orchestration, state machine, permission boundaries, artifact validation, trace, or audit.

## Version Boundary

V1.9 owns:

- CodeAgent switch UI in the middle panel.
- Session provider update API.
- Current CodeAgent display on the main page.
- Provider availability visibility for `mock`, `codex`, `opencode`, and `auto`.
- opencode as a selectable provider following the same provider contract.

V1.9 does not own:

- V1.7 cloud deployment topology.
- V1.8 Codex authentication hardening beyond reusing provider capability checks.
- A full provider marketplace.
- Silent fallback between real providers.
- Long-running streaming execution.

## Core Concept

AT separates three things that are often mixed together:

```text
Agent role       = main / analysis / code / test
CodeAgent        = mock / codex / opencode / auto
Provider runtime = the backend adapter that executes one bounded step
```

The UI label should be `CodeAgent`, not just `Provider`, because the user is deciding which code-agent capability AT should reuse.

## UI Placement

The CodeAgent switch belongs in the middle panel, near the document viewer.

Current layout:

```text
Left panel   = sessions + workspace tree
Middle panel = document viewer
Right panel  = run controls + state machine + evidence
```

V1.9 layout:

```text
Left panel
  sessions
  workspace tree

Middle panel
  CodeAgent Selector
  current selected CodeAgent
  provider availability summary
  document viewer

Right panel
  run controls
  state machine
  trace / audit / artifact / doctor evidence
```

The middle panel is the right place because provider choice is part of the session/document working context, while the right panel remains focused on execution and evidence.

## CodeAgent Selector

The selector shows:

```text
Current CodeAgent: codex
Resolved Mode: explicit
Availability: OK
Detail: command found: ...
Next Step: code
Next Step Provider: codex
```

Available choices:

```text
mock
auto
codex
opencode
```

Recommended visual behavior:

- `mock`: always available.
- `codex`: available if command is found; otherwise visible as `FAIL`.
- `opencode`: available if command is found; otherwise visible as `FAIL`.
- `auto`: visible as a routing mode, not a concrete process provider.

The user may select an unavailable provider, but the UI must make the risk visible. The runtime must not silently switch to another provider.

## Backend API

Add a session provider update endpoint:

```http
PATCH /api/sessions/{session_id}/provider
Content-Type: application/json

{
  "provider": "mock"
}
```

Allowed values:

```text
mock
auto
codex
opencode
```

Response:

```json
{
  "ok": true,
  "session": {
    "id": "session-id",
    "provider": "codex"
  }
}
```

Invalid provider response:

```json
{
  "error": {
    "code": "invalid_transition",
    "message": "Unknown provider: bad-provider",
    "retryable": false
  }
}
```

## Session Mutation Rules

Provider switching is allowed only when the session has no running step.

Rules:

- If any step is `running`, reject the switch.
- Done steps are not changed, replayed, or invalidated.
- Failed sessions may switch provider before retry.
- Pending future steps use the new provider value.
- `auto` uses `agent_providers` resolution.
- Explicit `mock`, `codex`, or `opencode` overrides `agent_providers`.
- No silent fallback is allowed.

This preserves state-machine integrity while still letting the user recover from a bad provider choice.

## Provider Capability Model

V1.9 reuses the provider capability shape:

```json
{
  "name": "opencode",
  "available": false,
  "provider_type": "process",
  "detail": "command not found: opencode"
}
```

The backend should expose provider capabilities in a frontend-friendly way. It can start by reusing `/api/doctor`, but the preferred V1.9 API is:

```http
GET /api/providers
```

Response:

```json
{
  "providers": [
    {
      "name": "mock",
      "available": true,
      "provider_type": "mock",
      "detail": "mock provider is always available"
    },
    {
      "name": "codex",
      "available": true,
      "provider_type": "process",
      "detail": "command found: /path/to/codex"
    },
    {
      "name": "opencode",
      "available": false,
      "provider_type": "process",
      "detail": "command not found: opencode"
    }
  ]
}
```

`auto` is not a provider command. It is a routing mode and should be shown separately or derived in the UI as a selectable mode.

## Resolved Provider Preview

The UI needs to show both selected mode and next actual provider.

Example:

```text
Selected CodeAgent: auto
Next Agent: code
Resolved Provider: codex
Availability: OK
```

Backend helper:

```text
resolve_agent_provider(config, session.provider, next_step.agent)
```

The Web Console can compute this if it has:

- active session provider
- next pending/runnable step
- provider capability list
- configured `agent_providers` preview from backend

For V1.9, keep this backend-owned to avoid duplicating config logic in the browser.

Preferred endpoint:

```http
GET /api/sessions/{session_id}/provider-status
```

Response:

```json
{
  "selected_provider": "auto",
  "next_agent": "code",
  "resolved_provider": "codex",
  "available": true,
  "detail": "command found: /path/to/codex"
}
```

## Frontend Components

Add:

```text
web/src/components/CodeAgentPanel.tsx
```

Responsibilities:

- render selected CodeAgent
- render resolved provider preview
- render capability status
- let user switch CodeAgent
- call backend update endpoint
- show unavailable status without hiding the option

Do not put provider switching into `RunControls`. `RunControls` should stay focused on execution commands:

```text
create session
run one step
continue
retry
refresh doctor
```

## Backend Components

Add to runtime service:

```text
RuntimeService.update_provider(session_id: str, provider: str) -> dict[str, Any]
RuntimeService.provider_status(session_id: str) -> dict[str, Any]
```

Add to app:

```text
PATCH /api/sessions/{session_id}/provider
GET /api/sessions/{session_id}/provider-status
GET /api/providers
```

The provider list endpoint must not execute providers. It only checks configuration and command discoverability.

## Error Handling

Provider switch errors:

- unknown session -> `session_not_found`
- unknown provider -> `invalid_transition`
- running step exists -> `invalid_transition`
- malformed payload -> `invalid_transition`

Provider availability errors:

- missing command -> visible `available: false`
- unsupported provider type -> visible `available: false`
- unknown provider -> visible `available: false`

None of these should crash the backend.

## Testing Strategy

Backend unit/API tests:

- `GET /api/providers` returns `mock`, `codex`, and `opencode`.
- `PATCH /api/sessions/{id}/provider` updates a waiting session.
- provider switch rejects unknown provider.
- provider switch rejects running session.
- provider status returns selected provider and resolved provider.
- `opencode` missing command is reported explicitly.

Frontend tests:

- CodeAgentPanel renders current selected CodeAgent.
- CodeAgentPanel renders provider availability.
- switching CodeAgent calls backend.
- unavailable opencode remains selectable but visibly marked `FAIL`.
- AppShell passes active session and provider status into CodeAgentPanel.

Integration tests:

- create mock session
- switch to `opencode`
- provider status shows `opencode`
- if `opencode` is missing, capability status is `FAIL`
- running a step fails through AT artifact/trace instead of silently falling back

## Success Criteria

V1.9 is complete when:

- the middle panel contains a CodeAgent switcher
- the main page shows current selected CodeAgent
- the backend can update session provider safely
- provider availability is visible
- opencode is selectable and diagnosed
- running sessions cannot change provider mid-step
- no silent provider fallback exists
- all backend tests pass
- all frontend tests pass
- frontend build passes

## Residual Risks

- opencode command behavior may differ by installed version.
- opencode authentication and non-interactive behavior may require a later hardening pass.
- Cloud servers may not have opencode installed.
- V1.9 makes opencode selectable and observable; it does not guarantee every opencode environment is ready.

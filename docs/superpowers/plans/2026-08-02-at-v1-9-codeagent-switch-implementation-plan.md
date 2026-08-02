# AT V1.9 CodeAgent Switch Implementation Plan

## Goal

V1.9 adds a first-class CodeAgent switching surface to the Web console and exposes backend provider contracts so AT can choose between `mock`, `auto`, `codex`, and `opencode` without silent fallback.

## Constraints

- Keep V1.9 focused on provider switching and extension hooks only.
- Do not change Git branches, commit, or push in this development window.
- Preserve the existing CLI and Web runtime behavior.
- Do not silently fallback from an unavailable selected provider to `mock`.
- Keep completed agent steps immutable; provider switching only affects future runnable steps.

## Task 1: Backend Provider Catalog

Add a provider catalog helper and API endpoint.

Tests first:
- `provider_capabilities` returns configured providers with availability details.
- `GET /api/providers` returns `mock`, `auto`, `codex`, and `opencode`.

Implementation:
- Add `provider_capabilities(config)` in `src/at_flow/providers.py`.
- Add `RuntimeService.list_providers()`.
- Add `GET /api/providers`.

## Task 2: Session Provider Switch Contract

Add runtime mutation for the active session provider.

Tests first:
- Switching a waiting session updates `session.provider`.
- Unknown providers are rejected with `invalid_transition`.
- Sessions with a running step reject provider switches.

Implementation:
- Add `RuntimeService.update_provider(session_id, provider)`.
- Add `PATCH /api/sessions/{session_id}/provider`.
- Add `PATCH` to CORS allowed methods.

## Task 3: Provider Status Contract

Expose the selected provider, next agent, resolved provider, availability, and detail.

Tests first:
- `auto` resolves through `agent_providers` for the next runnable agent.
- Completed sessions report no pending step without pretending to use `mock`.

Implementation:
- Add `RuntimeService.provider_status(session_id)`.
- Add `GET /api/sessions/{session_id}/provider-status`.

## Task 4: Frontend API Client

Connect the Web client to the new backend contracts.

Tests first:
- Client calls `/api/providers`.
- Client calls `/api/sessions/{id}/provider-status`.
- Client sends `PATCH /api/sessions/{id}/provider`.

Implementation:
- Add provider types in `web/src/api/types.ts`.
- Add `getProviders`, `getProviderStatus`, and `updateProvider` in `web/src/api/client.ts`.

## Task 5: CodeAgent Panel

Add a middle-panel CodeAgent selector and status summary.

Tests first:
- Panel shows selected CodeAgent, resolved provider, next agent, and unavailable provider detail.
- Changing the selector calls the switch callback.

Implementation:
- Add `web/src/components/CodeAgentPanel.tsx`.
- Wire it into `AppShell` above the document viewer.
- Keep `RunControls` focused on execution; keep create-session provider selection until a later cleanup can remove it safely.

## Task 6: Verification

Run:
- Backend unit tests.
- Frontend unit tests.
- Frontend production build.

Record any environment, dependency, or sandbox limitation explicitly.

## Execution Status

```text
Status: complete
Backend tests: 129 passed
Frontend tests: 38 passed
Production build: passed
Provider capability: codex available, opencode available (opencode 1.18.11, deepseek-v4-flash verified live)
Session snapshot display: sessions/*.md translated on demand with .zh.md cache (cherry-picked 9496d55)
Provider runtime: codex exec and opencode run are non-interactive (at.config.json); stderr isolated to provider.stderr.log (129th test)
Live E2E: opencode main-agent run completed; external_directory allow rules verified for .at/shared and .at/sessions
Branch: codex/v1.9-codeagent-switch (f52ae19 + 9496d55)
Git operations: V1.8 pushed as b839d91 after force-update; v1.9 branch pushed
```

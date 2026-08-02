# AT Flow Roadmap

This roadmap records the version boundary and execution order of AT Flow.

AT Flow is evolving from a local CLI runtime into a deployable multi-agent development platform. Each version owns one primary capability. Later versions may depend on earlier artifacts, but they should not smuggle their core mission into an earlier release.

## Version Timeline

| Version | Status | Mission |
| --- | --- | --- |
| V1.0 | Completed | Build the CLI shell and foundational multi-agent runtime. |
| V1.5 | Completed | Add a local Web Console over the same AT runtime. |
| V1.6 | Completed | Add provider routing and language contract support. |
| V1.7 | Current | Deploy AT Flow as a protected cloud demo. |
| V1.8 | Next | Reuse mature Codex code-agent capability through a stable provider contract. |
| V1.9 | Later | Extend the provider layer to opencode and other code agents. |

## Boundary Rule

```text
V1.7 owns deployment.
V1.8 owns Codex capability.
V1.9 owns provider expansion.
```

The project should not mix cloud deployment, Codex hardening, and opencode extension into one unstable release.

## Cross-Version Invariants

- AT Flow owns orchestration, state transitions, context construction, permission boundaries, artifact validation, trace, and audit.
- Providers execute bounded agent steps; providers do not own the AT state machine.
- There is no silent fallback between real providers.
- `mock` remains the safe local and cloud demo provider.
- Runtime failures must be visible through session state, trace, artifacts, audit, and Web Console errors.
- Secrets, API keys, CLI auth tokens, and server credentials must not be committed.
- Each version must have explicit mission, ownership, non-goals, verification gate, and known risks.

## Recommended Execution Order

```text
1. Keep V1.0, V1.5, and V1.6 as completed milestones.
2. Finish V1.7 cloud deployment with mock provider as the supported public demo path.
3. Verify the deployed Web Console, FastAPI backend, state machine, trace, audit, and artifact flow.
4. Start V1.8 Codex capability work after deployment is stable.
5. Start V1.9 opencode extension only after Codex provider behavior is explicit and observable.
```

## Documents

- [V1.0 Foundation](v1.0-foundation.md)
- [V1.5 Web Console](v1.5-web-console.md)
- [V1.6 Provider Language](v1.6-provider-language.md)
- [V1.7 Cloud Deployment](v1.7-cloud-deployment.md)
- [V1.8 Codex Capability](v1.8-codex-capability.md)
- [V1.9 opencode Extension](v1.9-opencode-extension.md)

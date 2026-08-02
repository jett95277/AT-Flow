# AT Flow Development Agent Notes

## Project Position

AT Flow 是个人辅助开发工具流，不是产品。开发决策以个人工作流效率、行为可
解释性和结果可验证性为准；不做产品化包装，不做面向大众用户的内容（新手引导、
营销文案、仅为演示效果的 UI 打磨等）。功能宁缺毋滥，克制的抽象和明确的职责
边界优先于覆盖面。

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
complete
```

Current V1.6 plan:

```text
docs/superpowers/plans/2026-08-01-at-v1-6-codex-provider-and-dual-entry-plan.md
```

Current V1.6 node:

```text
none
```

Last completed V1.6 node:

```text
Task 7: Full Verification
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

## Current V1.9 UI Remediation

```text
Status: complete
Plan: docs/superpowers/plans/2026-08-02-at-v1-9-ui-remediation-implementation-plan.md
Design: docs/superpowers/specs/2026-08-02-at-v1-9-ui-remediation-design.md
Current node: none
Last completed node: Task 7 - Integration and Regression Verification
```

## Current V1.9 CodeAgent Switch

```text
Status: complete
Plan: docs/superpowers/plans/2026-08-02-at-v1-9-codeagent-switch-implementation-plan.md
Design: docs/superpowers/specs/2026-08-02-at-v1-9-codeagent-switch-design.md
Current node: none
Last completed node: Task 6 - Verification
```

V1.9 codeagent-switch summary:

```text
Backend provider catalog and session switch contract:
  GET /api/providers -> mock/auto/codex/opencode with availability
  PATCH /api/sessions/{id}/provider -> typed invalid_transition guard
  GET /api/sessions/{id}/provider-status -> selected/next/resolved/available
Frontend: getProviders/getProviderStatus/updateProvider client methods and
CodeAgentPanel wired into AppShell above the document viewer.
No silent fallback: switching to an unavailable provider is rejected or
surfaced as unavailable detail, never replaced by mock.
Branch: codex/v1.9-codeagent-switch carries these changes.
Verification: backend 124 tests, frontend 38 tests, production build passed.
Live opencode run verified against deepseek-v4-flash (opencode 1.18.11).
```

Execution rules:

```text
1. Update this section before each development node.
2. Write the targeted test first and confirm the expected failure.
3. Implement only the behavior required by the failing test.
4. Run the targeted suite before moving to the next node.
5. After all UI nodes, run backend tests, frontend tests, build, and diff checks.
6. Do not create branches, commit, or push in this development window.
```

## Current V1.8 Corrective Remediation

```text
Status: complete
Plan: docs/superpowers/plans/2026-08-02-at-v1-8-language-and-agent-layout-remediation-plan.md
Design: docs/superpowers/specs/2026-08-02-at-v1-8-language-and-agent-layout-remediation-design.md
Current node: none
Last completed node: Task 7 - Current Workspace Migration, Documentation, And Full Verification
Expected tests: translation provider isolation, full backend, full frontend, production build, integration, sandbox, browser
Git operations: disabled in this development window
```

V1.8 completion addendum:

```text
Translation rules moved into a platform skill:
  .at/shared/skills/language-translation/SKILL.md  (execution rules)
  .at/shared/skills/language-translation/glossary.md (Chinese display terms)
ProcessTextTranslator loads the skill instructions when skill_dir is set;
missing SKILL.md raises translation_skill_missing (no fallback).
Fixed workspace documents have reviewed Chinese display copies:
  .at/agents/<agent>/agent.zh.md and output.zh.md
Shared docs also have Chinese display copies: memory/* and policies/*.
skills/SKILL.md files stay English (runtime instructions, not display docs).
WorkspaceService.read_file prefers the Chinese copy for zh, returns English
for language=en; the workspace tree hides *.zh.md copies whose source exists.
Frontend getFile requests language=zh.
Design: docs/superpowers/specs/2026-08-02-at-v1-8-language-translation-skill-design.md
Verification: backend 124 tests, frontend 41 tests, production build, real-data
read_file/tree check all passed. quick_validate.py not run (PyYAML missing);
live codex translation remains unverified in this environment.

Browser verification completed (2026-08-02): backend 8000 + frontend 3000
started, playwright browser session confirmed agents tree hides .zh copies and
the document viewer renders agent.md/output.md in Chinese with English terms
preserved. Mobile-width screenshots not captured.

Post-review cleanup: LanguageStatus UI panel removed per user request (it was
not part of the original requirements). Backend language API unchanged.
Frontend suite now 38 tests, production build passed.
```

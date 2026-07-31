# Baize AT Integration Design

## Purpose

AT Flow should absorb the strongest ideas from the Baize system without becoming a Claude-specific configuration clone. The target is an AT-native runtime design that keeps AT's current strengths: strict agent role boundaries, physical isolation, context contracts, memory proposals, trace/audit, and conversation-first state display.

The Baize ideas worth absorbing are:

- Topic mode for long-running work.
- Timeline-based memory.
- Session archive and save flow.
- SOP routing.
- Persona overlays.
- Startup summaries.
- Human-friendly interaction patterns.
- One-time approval for dangerous actions.

The integration must preserve this rule: Baize-inspired interaction improves how AT works with the user, but it must not bypass AT's state machine, permission model, or agent boundaries.

## Current AT Strengths

AT already has a reliable base:

- Four agent pipeline: `main -> analysis -> code -> test`.
- Each agent has isolated `agent.md`, `permissions.json`, `output.md`, `inbox`, `outbox`, and `workspace`.
- Session state is explicit and validated.
- Provider execution is isolated through minimal environment variables.
- `context.json` is generated per agent.
- Long-term memory updates go through proposal files.
- Protected path audit blocks unauthorized writes.
- Trace events record runtime nodes.
- Codex conversation mode shows AT state before provider execution.

These should remain the foundation.

## Baize Features To Absorb

### Topic Mode

Baize's topic model is valuable because it solves a real problem: long-running work does not fit cleanly into a single chat or a single session.

AT should add topic scope between shared memory and session memory:

```text
shared memory -> topic memory -> session memory -> agent context
```

Topic files:

```text
.at/topics/<topic-id>/
  topic.json
  context.md
  context_summary.md
  timeline.md
  sessions/
  artifacts/
  references/
```

Topic responsibilities:

- `topic.json`: structured metadata, name, status, created time, last active time, active session, tags.
- `context.md`: stable topic background.
- `context_summary.md`: small fast-loading summary for startup and switching.
- `timeline.md`: append-only chronological memory.
- `sessions/`: saved session summaries.
- `artifacts/`: important generated outputs.
- `references/`: supporting docs selected into context when needed.

### Timeline Memory

Timeline should be append-only and lightweight. It should not replace full artifacts.

Recommended format:

```text
2026-07-31 16:20 | session | 20260731-xxx | Completed context contract and memory proposal collection.
2026-07-31 16:40 | decision | baize-integration | Absorb topic, timeline, SOP, persona, and interaction ideas.
2026-07-31 17:10 | artifact | plan | Wrote AT runtime development plan.
```

Timeline entry types:

- `session`
- `decision`
- `artifact`
- `failure`
- `handoff`
- `memory`
- `approval`

The startup flow reads `context_summary.md` first. It reads `timeline.md` only when more history is needed. Full session archives are loaded last and only on demand.

### Session Archive

Baize's save-session flow should become an AT command:

```text
AT: save session
```

The archive should write:

```text
.at/topics/<topic-id>/sessions/<session-id>.md
```

Archive content:

- session id
- task
- topic
- final state
- agents run
- artifact paths
- failures
- decisions
- verification result
- next suggested action

Saving a session should also append a `session` entry to `timeline.md` and refresh `context_summary.md`.

### SOP Routing

Baize routes user intent to SOP files. AT should absorb this as a workflow-template router.

SOP files:

```text
.at/shared/sop/
  routing.json
  create-topic.md
  switch-topic.md
  save-session.md
  prd.md
  tech-design.md
  code-review.md
  bugfix.md
```

Routing behavior:

1. User message arrives in Codex.
2. AT checks trigger and current topic.
3. AT runs lightweight SOP matching before creating a session.
4. If exactly one SOP matches, the SOP becomes part of the `main` agent context.
5. If multiple SOPs match, AT asks the user to choose.
6. If none match, AT starts a normal session.

SOPs must not execute high-risk actions directly. They only shape the workflow and context.

### Persona Overlays

Baize's persona modes are useful, but AT must adapt them to agent boundaries.

AT should support:

```text
.at/shared/personas/
  default.md
  pm.md
  dev.md
  architect.md
  verifier.md
```

Persona overlay rules:

- `agent.md` remains the hard boundary.
- Persona can shape thinking style, output framing, and domain lens.
- Persona cannot grant permissions.
- Persona cannot move work from one agent role to another.
- Persona is recorded in `context.json`.

Examples:

```text
main + pm persona
analysis + architect persona
code + dev persona
test + verifier persona
```

### Human Interaction

The Baize interaction style is worth absorbing because it makes the assistant feel continuous across sessions.

AT should not become casual at the cost of clarity. It should use a structured but friendly interaction layer:

```text
AT FLOW
topic   : AT Runtime
session : 20260731-xxx
state   : ready

Recent Timeline
1. 16:20 Completed context contract
2. 16:40 Decided to absorb Baize topic/timeline/SOP/persona model
3. 17:10 Wrote runtime development plan

Suggested Next
- Continue current topic
- Start a new topic
- Save current session
```

Interaction rules:

- AT state machine still appears before provider execution.
- Startup panels should show active topic and recent timeline when available.
- If the user says `AT` alone, show the control panel plus topic summary.
- If the user says `继续 <topic>`, route to topic switch or topic continue.
- If the user says `保存`, route to save-session SOP.
- If a task is ambiguous, ask one structured question.
- Keep replies formal enough for engineering work, but less robotic than raw CLI output.

Baize's directness can be absorbed:

- conclusion first
- concise defaults
- uncertainty labeled explicitly
- clear next action
- no unnecessary capability explanation before AT state

Do not absorb:

- mandatory nickname rules
- automatic commit or push
- Claude-specific `.claude` coupling
- persona text that conflicts with AT's agent boundaries

### One-Time Dangerous Action Approval

Baize's `bash-guard` idea should become an AT-native approval guard.

Proposed structure:

```text
.at/approvals/
  pending/
  used/
```

Approval flow:

```text
AT approval required
action : delete files
risk   : destructive filesystem operation
token  : 8f31a2c0
reply  : AT: confirm 8f31a2c0
```

Rules:

- Token is single use.
- Token expires.
- Approval is scoped to one action, one session, and one command intent.
- Approval result is written to trace and timeline.
- Providers cannot self-confirm approvals.

## New Runtime Concepts

### Topic Registry

AT should maintain:

```text
.at/topics/index.json
```

Suggested schema:

```json
{
  "schema_version": 1,
  "active_topic": "topic-id",
  "topics": [
    {
      "id": "topic-id",
      "name": "AT Runtime",
      "path": ".at/topics/topic-id",
      "status": "active",
      "created_at": "2026-07-31T16:20:00+08:00",
      "last_active": "2026-07-31T17:10:00+08:00",
      "summary": "Building AT Flow runtime."
    }
  ]
}
```

### Topic-Aware Context Contract

`context.json` should gain:

```json
{
  "topic": {
    "id": "topic-id",
    "name": "AT Runtime",
    "summary_path": ".../context_summary.md",
    "timeline_path": ".../timeline.md",
    "selected_references": []
  },
  "persona": {
    "name": "dev",
    "path": ".at/shared/personas/dev.md"
  },
  "sop": {
    "name": "tech-design",
    "path": ".at/shared/sop/tech-design.md"
  }
}
```

The agent sees only selected topic files. The full topic directory is not automatically exposed.

### Topic Commands

Add commands:

```text
topic list
topic create <name>
topic switch <id|name>
topic status
topic timeline <id|name>
save-session <session-id>
```

Conversation aliases:

```text
AT: topics
AT: topic create <name>
AT: topic switch <id|name>
AT: continue topic <id|name>
AT: save session
```

### Startup Summary

When `AT` is triggered without a task:

1. Show AT ASCII panel.
2. Show active topic.
3. Show recent timeline entries.
4. Show current or latest session.
5. Show command menu.
6. Show Codex execution layer last.

## Data Flow

```text
User message
  -> Codex trigger
  -> AT conversation router
  -> topic router
  -> SOP router
  -> session creation or session continuation
  -> build_context
  -> agent provider
  -> artifact/proposal/audit/trace
  -> timeline/session archive update
  -> ASCII status output
```

## Error Handling

Topic errors:

- Missing topic index: initialize an empty topic registry.
- Missing active topic: run without topic and show `topic: none`.
- Ambiguous topic name: show candidates and ask user to choose.
- Corrupt topic metadata: mark topic unreadable and continue without loading it.

SOP errors:

- Missing SOP file: route as normal task and trace `sop_missing`.
- Multiple SOP matches: ask user to choose.
- Broken routing file: ignore SOP routing and trace `sop_routing_failed`.

Persona errors:

- Missing persona: fall back to `default.md`.
- Persona tries to grant permission: ignore permission-like instructions and keep `permissions.json` authoritative.

Approval errors:

- Expired token: reject and require a new approval.
- Used token: reject.
- Token does not match session/action: reject.

## Testing Strategy

Add focused tests before implementation:

- Topic registry initializes.
- Topic create writes `topic.json`, `context.md`, `context_summary.md`, `timeline.md`.
- Topic switch changes `active_topic`.
- Startup panel includes active topic and recent timeline.
- Session save writes topic session archive and appends timeline.
- Context contract includes selected topic summary, not topic root.
- SOP router matches one SOP, multiple SOPs, and no SOP.
- Persona overlay appears in context but does not alter permissions.
- Approval token is single-use and scoped.
- Dangerous action requires approval before execution.

## Development Plan Impact

The previous plan should be updated to this order:

1. State lifecycle and recovery.
2. Topic runtime.
3. Timeline and session archive.
4. Context selection contract v2.
5. SOP routing.
6. Persona overlay.
7. Memory proposal review/apply.
8. Artifact validation.
9. Observability commands.
10. Retry, abort, and reroute.
11. Approval guard.
12. Provider checks.
13. End-to-end scenarios.
14. ASCII polish.

## Non-Goals

- Do not import the damaged Baize markdown files directly.
- Do not depend on Baize's SQLite database.
- Do not introduce Bash as a required runtime dependency.
- Do not add automatic commit or push.
- Do not replace AT's four-agent architecture.
- Do not let persona or SOP files override `permissions.json`.

## Open Decision

The only open product choice is tone:

- AT can stay formal and structured while borrowing Baize's continuity features.
- AT can become warmer and more assistant-like in startup/status text.

Recommendation: use a formal default, with slightly warmer startup/status phrasing. Engineering commands and failure reports should stay precise.

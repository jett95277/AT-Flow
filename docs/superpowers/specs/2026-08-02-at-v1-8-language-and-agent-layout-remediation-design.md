# AT V1.8 Agent Layout And Language Remediation Design

## Status

Approved for implementation on 2026-08-02. This is a corrective V1.8 patch.
The original language contract was introduced in V1.6, while V1.8 owns Codex
capability visibility. The patch closes the unfinished language behavior without
changing the version ownership of V1.9 provider switching.

## Problem

Two contracts are incomplete:

1. Agent definitions are stored under `.at/shared/agents`, even though
   `agent.md`, `permissions.json`, and `output.md` are platform-owned role
   definitions rather than shared collaboration files. The Web Console only
   hides the duplicate tree entry; the physical model remains ambiguous.
2. The language adapter writes `language.json`, but it does not translate. It
   wraps the original Chinese task in English instructions and leaves
   `translation_status` as `pending`. The frontend also reads the English source
   artifact directly, so the promised Chinese-display/English-runtime contract
   is not implemented.

## Goals

- Move canonical Agent definitions to `.at/agents/<agent>`.
- Keep immutable-by-convention Session snapshots at
  `.at/sessions/<id>/agents/<agent>`.
- Keep `.at/shared` limited to shared memory, skills, policies, documents,
  inbox material, and proposals.
- Translate a Chinese user task into a real English runtime task before the
  first Agent prompt is built.
- Keep runtime prompts, source artifacts, and downstream handoffs in English.
- Produce a Chinese display artifact for the Web Console without modifying the
  English source artifact.
- Record translation provider, status, timestamps, and failures.
- Fail explicitly when required translation is unavailable. Do not silently
  reuse Chinese text as an English runtime task.

## Non-Goals

- Exposing hidden chain-of-thought or forcing a model's private reasoning
  language.
- Adding a translation microservice or requiring an OpenAI API key.
- Replacing Codex as the preferred code-agent provider.
- Reworking V1.9 provider switching.
- Automatically migrating arbitrary external AT workspaces without an explicit
  command.

## Agent Definition Layout

The canonical runtime layout becomes:

```text
.at/
  agents/
    main/
      agent.md
      permissions.json
      output.md
    analysis/
    code/
    test/
  shared/
    memory/
    skills/
    policies/
    docs/
    inbox/
    proposals/
  sessions/
    <session-id>/
      agents/
        <agent>/
```

`workspace.agents_dir` defaults to `.at/agents`. The current workspace is moved
explicitly. A migration command reports the source and target and refuses to
overwrite a non-empty target. Loading an old configured workspace continues to
honor its explicit `agents_dir`; AT does not silently reinterpret that path.

The Web Console exposes three logical roots:

- `agents`: canonical Agent definitions.
- `shared`: shared collaboration files only.
- `sessions`: Session state and Agent snapshots.

## Language Contract V2

`language.json` remains the persisted contract and is upgraded to schema version
2. It separates input translation from display translation:

```json
{
  "schema_version": 2,
  "source_language": "zh",
  "runtime_language": "en",
  "display_language": "zh",
  "task_original": "中文任务",
  "task_runtime": "English task",
  "input_translation": {
    "status": "completed",
    "provider": "codex",
    "error": null
  },
  "display_translation": {
    "status": "pending",
    "provider": "codex",
    "error": null
  }
}
```

Allowed translation statuses are `disabled`, `not_required`, `pending`,
`running`, `completed`, and `failed`. A completed input translation must contain
non-empty text different from the Chinese source when the source and runtime
languages differ.

## Translation Boundary

The language package owns a narrow interface:

```text
translate(text, source_language, target_language, purpose) -> translated text
```

The implementation uses an explicitly configured AT provider through a
restricted translation execution context. Translation receives text and the
language policy only; it receives no project path, shared memory, Agent inbox,
or write permission. Tests inject a deterministic translator. Production may
select Codex or another configured provider.

The prompt-language Skill remains a declarative policy and glossary. It does not
perform translation and must not mark a translation complete.

## Runtime Flow

### Session Input

1. The frontend submits the original Chinese task.
2. AT stores the original task unchanged in Session state.
3. Before the first Agent step, Language Service creates or resumes
   `language.json`.
4. If source and runtime languages differ, the configured translation provider
   produces `task_runtime`.
5. Translation status and trace events are persisted before Agent execution.
6. A required translation failure fails the queued Agent step with a retryable
   language error; the provider is not called with a disguised fallback task.

### Agent Execution

1. `build_prompt` uses `task_runtime` as the executable task.
2. The original Chinese task remains persisted in `language.json` and Session
   metadata but is omitted from the provider prompt after successful
   translation.
3. `artifact.md` is the English source artifact used by downstream Agents.
4. Handoffs route only the English source artifact.

### Frontend Display

1. After an English artifact is collected, Language Service creates
   `artifact.zh.md` when display and runtime languages differ.
2. The artifact API returns source text, display text, languages, and
   translation status as structured data.
3. The Web Console shows Chinese display text when status is `completed`.
4. On translation failure, the UI shows an explicit failure and labels any
   optional English source view as source text. It does not silently present
   English as translated Chinese.

## Configuration

Language behavior is explicit:

```json
{
  "language": {
    "enabled": true,
    "source": "zh",
    "runtime": "en",
    "display": "zh",
    "translation_provider": "codex",
    "translation_provider_overrides": {
      "command": [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--color",
        "never",
        "-"
      ],
      "timeout_seconds": 180
    },
    "required": true,
    "translate_artifacts": true
  }
}
```

`enabled: true` and `required: true` are current-project settings. A fresh
workspace keeps language conversion disabled until a translation provider is
configured, so local `mock` execution never pretends to translate. Tests that do
not exercise translation use the disabled default, equal source/runtime
languages, or an injected translator. The platform does not choose a different
provider when the configured provider is unavailable.

Translation provider overrides are deliberately narrow: only `command` and
`timeout_seconds` are consumed. The adapter always forces stdin prompt mode, a
minimal environment, and its own translation working directory.

## Errors And Observability

Language failures use typed error codes:

- `translation_provider_unavailable`
- `input_translation_failed`
- `display_translation_failed`
- `invalid_translation_output`

Trace records translation lifecycle events, including purpose and provider but
excluding secret values. `language.json` contains the durable status. On a
successful process, stderr is written to the translation work directory as
`provider.stderr.log` and is never appended to translated content. On a failed
process, the typed provider error remains visible and retryable where allowed.

## Testing

Each implementation node starts with a failing test.

- Workspace tests verify new defaults, explicit migration, collision refusal,
  and absence of physical `.at/shared/agents` after migration.
- Language unit tests verify real translated output from an injected translator,
  no-op behavior for equal languages, status persistence, retry, and invalid
  output rejection.
- Prompt tests verify successful bilingual sessions contain no original Chinese
  task in the provider prompt and use the English runtime task.
- Runtime tests verify translation failure prevents Agent provider execution.
- Artifact tests verify English handoff and separate Chinese display artifact.
- API and frontend tests verify structured language status and explicit failure
  display.
- Final verification runs backend tests, frontend tests, frontend production
  build, integration checks, and sandbox checks.

## Risks

- Translation consumes tokens before and after Agent execution, so English
  prompts do not automatically reduce total token usage. The benefit is a stable
  English runtime contract, not guaranteed cost reduction.
- Provider translation quality is model-dependent. Persisting source and
  translated text keeps the result auditable.
- Codex CLI non-interactive behavior is environment-dependent. Unit and sandbox
  tests validate the adapter boundary. The current machine completed a real
  read-only `codex exec` call, but WebSocket timeout retries caused significant
  latency before Codex explicitly fell back to HTTPS.
- Existing external workspaces may still point to `.at/shared/agents`. They need
  the explicit migration command and config update.

## Acceptance Criteria

- A fresh workspace creates `.at/agents` and does not create
  `.at/shared/agents`.
- The current workspace is explicitly migrated without losing Agent contract
  files.
- A Chinese task produces a persisted English `task_runtime` through a configured
  translator before Agent execution.
- A successful Agent prompt uses English task text and omits the original
  Chinese task.
- Downstream Agents consume English `artifact.md`.
- The Web Console can display `artifact.zh.md` and translation status.
- Missing or failed translation is visible in state, trace, API, and UI, with no
  silent fallback.
- All targeted, full, integration, and sandbox tests pass before completion is
  reported.

# AT Runtime Contracts

This document records the runtime layer that matters more than the ASCII panel:
state schema, transitions, context, memory proposals, artifacts, trace, errors,
audit, and retry.

## Session Schema

Every `state.json` uses schema version `1`.

Required session fields:

- `schema_version`
- `id`
- `task`
- `project_path`
- `provider`
- `created_at`
- `updated_at`
- `status`
- `current_stage`
- `failure_reason`
- `steps`

Session statuses:

- `queued`
- `running`
- `done`
- `failed`
- `aborted`

Each step records:

- `agent`
- `status`
- `started_at`
- `finished_at`
- `artifact_path`
- `error`
- `failure_reason`
- `retry_count`
- `max_retries`
- `retryable`
- `input_paths`

## Stage Transitions

Allowed step transitions:

```text
queued   -> running
retrying -> running
running  -> done
running  -> failed
failed   -> retrying
failed   -> aborted
```

Invalid jumps, such as `queued -> done`, raise `TransitionError`.

## Artifact Contract

Each agent directory may contain:

- `context.json`: agent-local copy of the current context contract
- `input.json`: structured input contract for the current step
- `prompt.md`: prompt sent to the provider
- `outbox/artifact.md`: successful output
- `outbox/failure.json`: structured failure output
- `outbox/proposals/`: requested shared-memory or policy updates
- `outbox/logs/`: provider-side supporting logs

Each agent's `output.md` defines required artifact sections. After a provider
returns, AT validates `outbox/artifact.md` before marking the step complete.

If required sections are missing:

- AT writes `outbox/failure.json`
- the step is marked `failed`
- the failure is retryable
- trace records `artifact_contract_failed`
- handoff is not routed to the next agent

## Context Contract

Before each provider run, AT writes:

```text
.at/sessions/<session-id>/context/<agent>.json
```

The context contract is the source of truth for what the agent may see. It
includes the task, agent, step index, permission summary, contract file paths,
authorized inbox/outbox/workspace paths, authorized shared files, authorized
project path if granted, and input artifact paths.

It does not include workspace root, shared root, session root, shared directory
paths, or other agent private directories.

Process providers receive this file through:

```text
AT_CONTEXT
```

Authorized shared files are listed in `selected_files`:

```json
{
  "selected_files": {
    "shared_memory": [".../.at/shared/memory/user.md"],
    "shared_skills": [],
    "shared_policies": [],
    "shared_docs": [],
    "shared_inbox": []
  }
}
```

Legacy `AT_SHARED_MEMORY`, `AT_SHARED_SKILLS`, and `AT_SHARED_INBOX`
environment variables are present but empty. Providers must use `AT_CONTEXT`
instead of shared directory environment variables.

## Provider Contract

AT treats Codex, opencode, OpenAI API, and mock execution as provider adapters.
Providers execute exactly one bounded agent step; they do not own the session
state machine.

Process providers such as Codex CLI and opencode must follow this boundary:

- AT invokes the provider only after writing the agent package, `context.json`,
  `input.json`, and `prompt.md`.
- The provider current working directory is the agent private `workspace`.
- The provider receives the prompt through the configured `prompt_mode`.
- The provider receives a minimal environment by default.
- The provider returns text output; AT collects it into `outbox/artifact.md`.
- The provider cannot advance AT state directly.
- The provider cannot mutate shared memory directly; it can only write proposals.
- AT audits filesystem changes after the provider returns.

Codex is the preferred mature code-agent provider for implementation and
verification work, but AT remains the orchestrator. `agent.md` restricts role
and side effects; `permissions.json`, private workspace layout, context
construction, audit, artifact validation, and transition rules enforce the hard
boundary.

Provider selection has two modes:

- Explicit provider mode: `mock`, `codex`, or `opencode` means every agent step
  uses that provider unless the session is changed explicitly.
- Auto provider mode: `auto` means AT resolves each agent through
  `agent_providers`; missing routes fall back to `default_provider` or `mock`.

AT must not silently override an explicit session provider with an agent route.

When `language.json` contains `task_runtime`, AT uses it as the primary `Task`
inside provider prompts. The original user task is preserved separately as
`Original User Task` and in `language.task_original`.

## Memory Contract

Shared long-term memory is initialized under:

```text
.at/shared/memory/
  user.md
  project.md
  decisions.md
  rules.md
```

Shared policies are initialized under:

```text
.at/shared/policies/
  context.md
  memory.md
```

Agents may request long-term memory updates by writing files under:

```text
.at/sessions/<session-id>/agents/<agent>/outbox/proposals/
```

AT collects those files into:

```text
.at/sessions/<session-id>/memory-proposals/<agent>-*.md
```

Agents do not directly mutate `.at/shared/memory`.

## Trace Contract

Each session writes:

```text
.at/sessions/<session-id>/trace.jsonl
```

Important trace events:

- `prepare_agent`
- `route_prior_handoff`
- `build_context`
- `transition_state`
- `run_agent_start`
- `run_agent_done`
- `run_agent_failed`
- `collect_output`
- `artifact_contract_failed`
- `collect_memory_proposals`
- `audit_permissions`
- `route_handoff`

Each event includes timestamp, session id, agent, step index, status, detail, and
optional structured data.

Trace can be inspected with:

```powershell
python .\at.py trace <session-id>
```

Audit can be inspected with:

```powershell
python .\at.py audit <session-id>
```

Artifacts or failures can be inspected with:

```powershell
python .\at.py artifact <session-id> <agent>
```

Workspace health can be inspected with:

```powershell
python .\at.py doctor
```

## Packaging Entry

AT can be enabled in a target project with one command:

```powershell
python -m at_flow enable --target <project-root>
```

When installed as a package, the console script is:

```powershell
at enable --target <project-root>
```

The command initializes `at.config.json`, creates `.at/`, and installs the Codex
trigger block in `AGENTS.md`. The default trigger command is `python -m at_flow`
so it works after package installation without relying on a source-tree
`at.py`.

## Error Contract

Provider failures write `outbox/failure.json` and mark the step as failed.

Audit failures also write `outbox/failure.json`, but are not retryable by
default because they indicate a permission boundary violation.

## Retry Contract

The first failed step can be retried with:

```powershell
python .\at.py retry <session-id> --format chat
```

Retry changes:

```text
failed -> retrying -> running
```

The default retry limit is one retry per step.

Before the provider runs again, AT clears the retried agent's previous `outbox`
contents so stale `artifact.md`, `failure.json`, proposals, or logs cannot be
reused as the new attempt's evidence. AT recreates the standard `proposals/` and
`logs/` directories after cleanup.

## Recovery Contract

When `Runner.run()` loads a session that already contains a `running` step, AT
treats that step as interrupted work from a previous process.

Recovery behavior:

- mark the first interrupted step as `failed`
- keep the failed step retryable
- record the reason in `failure_reason`
- write a `recover_interrupted_step` trace event
- save the session and stop before running any provider

The user must then explicitly retry the failed step.

## Verification Scenarios

The test suite covers:

- schema validation
- invalid transition rejection
- trace generation
- context contract generation
- file-level shared context authorization
- artifact contract validation
- memory proposal collection
- structured failure artifact
- provider failure
- interrupted step recovery
- retry recovery
- audit failure
- trace/audit/artifact/doctor CLI output
- shared write rejection
- cross-agent write rejection
- minimal project write for `code`
- empty `AT` control panel

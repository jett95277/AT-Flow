# Prompt Language Policy

Use this skill when an AT provider, prompt builder, or agent profile needs to
separate user-facing Chinese display from English runtime execution.

This Skill defines language policy only. It does not perform translation.
`LanguageService` owns provider invocation, status persistence, retry behavior,
artifact generation, and failure reporting.

## Policy

- Use English for agent runtime prompts, reasoning instructions, and `artifact.md`.
- Use Chinese for user-facing summaries and Web Console display.
- Keep runtime trace and audit details in English; keep original user text only
  in the Session language contract.
- Do not translate paths, command names, API names, code identifiers, or file names.
- Prefer `artifact.zh.md` or `summary.zh.md` for display when available.
- If Chinese display translation fails, show an explicit failure and expose the
  English source only as a labelled source artifact. Never copy it into the
  Chinese display field.

## Artifact Convention

```text
artifact.md      English source artifact for downstream agents
artifact.zh.md   Chinese display artifact for frontend users
summary.zh.md    Optional concise Chinese display summary
```

## Runtime Contract

Every session may contain:

```text
.at/sessions/<session-id>/language.json
```

Every agent `context.json` should include:

```json
{
  "language": {
    "runtime_language": "en",
    "display_language": "zh",
    "task_runtime": "..."
  }
}
```

`task_original` must not enter provider-facing `context.json` or `prompt.md`
after translation. It remains in `state.json` and `language.json` for audit.

## Execution Boundary

- Input translation: Chinese task -> English `task_runtime` before Agent run.
- Runtime handoff: English `artifact.md` only.
- Display translation: English `artifact.md` -> Chinese `artifact.zh.md`.
- Translation process: minimal environment, translation-only working directory,
  no project/shared/Agent control paths injected through environment or context,
  and successful stderr stored separately. Literal paths already present in the
  source artifact are preserved as source text.
- Required input translation failure: current step fails retryably and no Agent
  provider is invoked.
- Display translation failure: engineering step stays done, but the failure is
  visible in `language.json`, trace, API, and Web Console.

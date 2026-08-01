# Prompt Language Policy

Use this skill when an AT provider, prompt builder, or agent profile needs to
separate user-facing Chinese display from English runtime execution.

## Policy

- Use English for agent runtime prompts, reasoning instructions, and `artifact.md`.
- Use Chinese for user-facing summaries and Web Console display.
- Keep trace and audit in the original execution language.
- Do not translate paths, command names, API names, code identifiers, or file names.
- Prefer `artifact.zh.md` or `summary.zh.md` for display when available.
- If no Chinese display artifact exists, show the English source and mark it as source text.

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
    "task_original": "...",
    "task_runtime": "..."
  }
}
```

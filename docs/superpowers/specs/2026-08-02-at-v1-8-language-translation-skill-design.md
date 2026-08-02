# AT V1.8 Language Translation Skill Design

## Status

Draft for V1.8 completion. This spec adds a translation execution skill to the
V1.8 language pipeline. It does not change the pipeline contract; it changes
where translation instructions live.

## Problem

V1.8 implemented a real Chinese-input / English-runtime / Chinese-display
pipeline. Translation instructions are currently hard-coded in
`src/at_flow/language/translator.py::_translation_prompt()`. The user's core
requirement is the platform mechanism itself (frontend Chinese display, runtime
English prompt, English provider input). Translation rules should be a
maintainable, reusable platform skill instead of Python code, so every
translation point in AT invokes the skill.

## Scope Boundary

This skill is an AT platform resource only. It is loaded by `LanguageService`
at the two fixed translation points:

1. Input translation: Chinese task -> English `task_runtime`.
2. Display translation: English `artifact.md` -> Chinese `artifact.zh.md`.

Fixed workspace documents (agent.md, output.md) are translated once into static
Chinese display copies (`agent.zh.md`, `output.zh.md`) and served from disk.
They do not go through runtime translation, so no provider call or cache
eviction is needed for them.

It is NOT a Codex global skill. Conversational translation between the user and
Codex is out of scope: the model natively understands both languages, and an
extra translation call there wastes tokens and latency. This is an explicit
non-goal.

## Goals

- Move translation instructions out of Python into a platform skill.
- Keep the two translation call points and their semantics unchanged.
- Keep `LanguageService` status, retry, audit, and persistence unchanged.
- Fail explicitly when the skill is missing; never silently fall back to the
  hard-coded prompt or to the original text.
- Make translation rules editable without touching Python.
- Serve Chinese display copies of fixed workspace documents from disk, with
  zero runtime token cost and no provider dependency.

## Non-Goals

- Adding a Codex global skill or conversational translation capability.
- Changing the English-runtime contract.
- Adding translation dependencies or a microservice.
- Changing provider availability or routing.
- Runtime translation of fixed workspace documents on every read.

## Skill Structure

New directory under the AT shared skill area:

```text
.at/shared/skills/language-translation/
  SKILL.md      # translation execution instructions
  glossary.md   # domain term zh/en pairs, consulted by the translator
```

This mirrors the existing `prompt-language-policy` layout. No `agents/openai.yaml`
is created because this is an AT runtime resource, not a Codex-discoverable
global skill.

## SKILL.md Content

Frontmatter contains only `name` and `description`. The description states the
trigger: use when AT needs to translate text between runtime and display
languages while preserving paths, commands, API names, code identifiers, code
blocks, and file names.

Body covers:

- Role: restricted translator for the AT language contract.
- Inputs: `source_language`, `target_language`, `purpose` (`task` or
  `artifact`), and the text to translate.
- Output contract: return only the translated text. No commentary, no Markdown
  fences, no prefixes or suffixes.
- Preservation rules: paths, commands, API names, code identifiers, code
  blocks, and file names are preserved exactly as literals.
- Purpose semantics: `task` produces an English runtime task from the user's
  Chinese input; `artifact` produces a Chinese display copy from the English
  source artifact.
- Failure semantics: when translation cannot be performed, fail explicitly;
  never return the source text as translated output.

## Glossary

`glossary.md` holds optional domain term pairs (zh -> en, en -> zh). The
translator prompt instructs the provider to prefer glossary terms when they
apply. The glossary starts with terms used by the AT platform itself and can be
extended per project without code changes.

## AT Integration

`ProcessTextTranslator.translate()` loads the skill before building the prompt:

- Skill root resolves to `<workspace>.at/shared/skills/language-translation`.
- `SKILL.md` content is prepended to the translation prompt as instructions.
- `glossary.md` is appended as a reference when present.
- A missing skill directory or missing `SKILL.md` raises a typed
  `TranslationError` (`translation_skill_missing`, not retryable). No fallback
  to the hard-coded prompt.

The translation boundary remains unchanged: minimal environment, translation-only
working directory, no project/shared/Agent control paths, stderr in a separate
log, stdin prompt mode.

## Fixed Document Display

`WorkspaceService.read_file(path, language="zh")` prefers a static Chinese
display copy when one exists:

```text
agents/main/agent.md      -> agents/main/agent.zh.md  (served for zh)
agents/main/output.md     -> agents/main/output.zh.md (served for zh)
agents/main/permissions.json -> no copy, JSON stays English
```

- The copy rule applies to `.md` files only; JSON configuration stays English.
- `language=en` bypasses the copy and returns the source file.
- The workspace tree hides `*.zh.md` copies when the matching source exists, so
  users see one document per contract.
- Copies are generated once (by the platform owner or a contributor) and
  reviewed; runtime does not regenerate them.

## Behavior Matrix

```text
translation point       language flow                         status on success
input (task)            zh -> en task_runtime                 input_translation.completed
display (artifact)      en -> zh artifact.zh.md               display_translation.completed
skill missing           no translation attempt                typed error, step failed retryable=false (input) / display failed (artifact)
provider failure        no translated output                  retryable failed state (input) / display failed (artifact)
```

## Testing

- Translator unit tests: prompt contains the SKILL.md instructions; glossary is
  included; missing skill raises the typed error; existing translation behavior
  still passes with the skill present.
- Workspace tests: `read_file` prefers the Chinese copy for `zh`, returns the
  source for `en`, and the tree hides translation copies.
- Client tests: `getFile` requests `language=zh`.
- Regression: full backend suite, full frontend suite, production build.
- Real Codex translation remains an independent verification item because live
  translation execution has not succeeded in this environment yet.

## Documentation Updates

- `docs/architecture.md`: describe the skill as the translation instruction
  source for the language pipeline.
- `docs/runtime-contracts.md`: document `translation_skill_dir` and the skill
  loading contract.
- V1.8 remediation plan: mark the skill work as part of Task 7 completion.
- `README.md` and `agent.md`: record the skill location and the no-fallback rule.

## Risks

- The skill adds a small amount of prompt text (roughly 200-400 tokens per
  translation call). This is an explicit cost paid for maintainability.
- Translation quality remains model-dependent; the glossary narrows but does not
  eliminate variance.
- Live `codex exec` translation has failed with transport errors in this
  environment; that is tracked separately and reported honestly.

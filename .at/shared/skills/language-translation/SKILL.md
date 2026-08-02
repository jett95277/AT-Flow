---
name: language-translation
description: Translate text for the AT language contract between Chinese display and English runtime. Use when AT needs to translate a user task from Chinese to English, translate an English artifact into a Chinese display copy, or translate fixed workspace documents (agent.md, output.md) for Chinese frontend display. Preserves paths, commands, API names, code identifiers, code blocks, file names, and glossary terms.
---

# Language Translation

Translate text for the AT language contract between display and runtime
languages. This skill is loaded by `LanguageService` at every platform
translation point. Follow the rules exactly; do not improvise.

## Inputs

- `source_language`: language of the input text (for example `zh`, `en`)
- `target_language`: language of the translated output (for example `en`, `zh`)
- `purpose`: one of `task`, `artifact`, `document`
- `text`: the text to translate

## Output Contract

Return only the translated text:

- Output exactly one translation. No commentary, no Markdown fences, no
  prefixes, no suffixes.
- Preserve paths, commands, API names, code identifiers, code blocks, file
  names, and URLs exactly as they appear.
- Prefer terms from `glossary.md` when they apply; keep core technical nouns
  such as `agent`, `artifact`, `provider`, and `prompt` in English.
- Never return the source text as translated output when the languages differ.

## Purpose Semantics

- `task`: translate the user's Chinese task into an English runtime task
  (`task_runtime`). Only the runtime task enters provider prompts.
- `artifact`: translate the English source `artifact.md` into a Chinese display
  copy `artifact.zh.md`. Display only; downstream handoff keeps the English
  source.
- `document`: translate a fixed workspace document (for example `agent.md`,
  `output.md`) into a Chinese display copy for the frontend. JSON configuration
  files are not translated.

## Failure

When translation cannot be completed reliably, fail explicitly. Never silently
reuse the source text or claim a translation that was not produced.

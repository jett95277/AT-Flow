# AT Runtime Trigger

<!-- AT_FLOW_TRIGGER_BEGIN -->

This project is AT Runtime (v2.x): a **memory layer** for personal AI-assisted
development workflows. AT manages three-tier memory (short / medium / long) —
visibility, manual operations, and lifecycle. It does NOT orchestrate agents;
workflow / knowledge / execution are reused from open source.

## Trigger Rules

When the user's message is exactly one of:

- `AT`
- `AT:`
- `AT：`

run `at doctor` and show the JSON report as the AT control panel:

```powershell
python "E:\AT FLOW\.venv\Scripts\at.exe" doctor
```

When the user's message starts with `AT:` or `AT：`, treat it as an AT command.
All commands run with cwd = the project root.

## Command Mapping (memory layer)

- `AT: doctor` -> `python "E:\AT FLOW\.venv\Scripts\at.exe" doctor`
- `AT: memory write, <memory-uri>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" memory write <memory-uri> --conclusion "<text>" [--constraint "<text>"]... [--unresolved "<text>"]... [--task <id>] [--project <name>]`
- `AT: memory get, <memory-uri>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" memory get <memory-uri>`
- `AT: memory view` -> `python "E:\AT FLOW\.venv\Scripts\at.exe" memory view`
- `AT: memory promote, <memory-uri>, [to <tier>]` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" memory promote <memory-uri> [--to medium|long]`
- `AT: memory archive, <memory-uri>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" memory archive <memory-uri>`
- `AT: memory discard, <memory-uri>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" memory discard <memory-uri>`
- `AT: memory checkpoint, <label>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" memory checkpoint <label>`
- `AT: memory timeline` -> `python "E:\AT FLOW\.venv\Scripts\at.exe" memory timeline`
- `AT: memory rollback, <node>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" memory rollback <node>`

## Memory Write Convention (stage completion)

At the end of each development stage, Codex should call `at memory write` to
persist structured memory into the three-tier store:

- `--conclusion`: what was decided / found
- `--constraint`: hard constraints discovered (repeatable)
- `--unresolved`: open questions / risks (repeatable)
- `--task` / `--project`: ownership used later by `promote --to` for scope
  migration (session -> task -> project)

Write to `memory://session/<id>/short` at stage completion; the human decides
whether to promote to medium / long via `at memory promote`.

## Memory Read Convention

When a later session needs prior context, call
`at memory get <memory-uri>` to read structured entries; do not read
`.agent/memory/` files directly.

## Checkpoint Skill

When the user says "打点", "记录时间节点", "存个档", or "checkpoint", use the
`at-memory-checkpoint` skill to run `at memory checkpoint <label>`.

## Context Bundle Note

Context Bundle / Handoff / policy orchestration are V0.1 verification
artifacts (kept in code, out of the v2.1 core). The memory layer only owns
three-tier memory storage, structured write/read, tree view, manual
promote/archive/discard, timeline checkpoint/rollback, and audit events.

<!-- AT_FLOW_TRIGGER_END -->

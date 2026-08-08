# AT Runtime Trigger

<!-- AT_FLOW_TRIGGER_BEGIN -->

This project is AT Runtime (v2.0): a context-isolated runtime for long-running
and parallel coding agents. AT owns Context / Memory / Scope / Handoff;
Codex is the execution layer.

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

## Command Mapping (v2)

- `AT: init` -> `python "E:\AT FLOW\.venv\Scripts\at.exe" init`
- `AT: doctor` -> `python "E:\AT FLOW\.venv\Scripts\at.exe" doctor`
- `AT: task run, <task-id>, <goal>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" task run <task-id> "<goal>" --provider mock`
- `AT: context inspect, <session-id>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" context inspect <session-id>`
- `AT: memory inspect, <memory-uri>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" memory inspect <memory-uri>`
- `AT: handoff inspect, <handoff-id>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" handoff inspect <handoff-id>`
- `AT: eval, <demo-task>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" eval "<demo-task>"`

If a command needs a `<session-id>` / `<handoff-id>` and the user did not
provide one, list candidates from `.agent/runtime/sessions/` and
`.agent/handoffs/` under the project root.

## Context Bundle Concept

AT builds a fresh Context Bundle for every session; context is never inherited
from a previous conversation. A bundle contains:

- `task` (id, goal) and `role` (type)
- `constraints` and `handoff` (from previous agent, summary + ref)
- `evidence` (file refs), `relevant_memory` (memory:// refs), `knowledge`
- `token_budget` and `provenance`

Agents only exchange results through structured Handoffs; they do not share
conversations. Short memory is per-session; medium memory is task/feature
scoped; long memory is project scoped and requires promotion.

<!-- AT_FLOW_TRIGGER_END -->

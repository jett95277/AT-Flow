

# AT Flow Trigger

<!-- AT_FLOW_TRIGGER_BEGIN -->

This project has AT Flow enabled.

AT is a conversation-controlled multi-agent runtime. The user-facing interface is
the Codex conversation. The CLI command is only the background runtime.

## Usage Modes

AT has two official usage modes:

1. Codex Conversation Mode: the user works inside Codex chat; AT renders status
   first and then uses Codex/provider as the execution layer.
2. Web Console Mode: the user works in the browser; the backend calls the same
   AT runtime, session state, provider adapters, artifacts, trace, and audit.

AT state machine must be shown before Codex/provider execution. Codex is a
mature code-agent provider, but AT owns orchestration, state transitions,
permission boundaries, handoff, artifact validation, trace, and audit.

## Trigger Rules

When the user's message is exactly one of these:

- `AT`
- `AT:`
- `AT：`

do not answer conversationally. Run this command and show its output exactly as
the AT ASCII control panel:

```powershell
python "E:\AT FLOW\at.py" --root "E:\AT FLOW" panel --format chat
```

When the user's message starts with `AT:` or `AT：`, treat it as an AT command.
Keep the display order strict:

1. AT state machine
2. Current stage
3. Stage details
4. Codex execution layer

Do not describe Codex capabilities before the AT state machine.

## Command Mapping

Use these mappings:

- `AT: init` -> `python "E:\AT FLOW\at.py" --root "E:\AT FLOW" init`
- `AT: status` -> `python "E:\AT FLOW\at.py" --root "E:\AT FLOW" panel --format chat`
- `AT: list` -> `python "E:\AT FLOW\at.py" --root "E:\AT FLOW" list --format chat`
- `AT: next` -> run the current session one step with `run <session-id> --one-step --format chat`
- `AT: continue` -> run the current session with `run <session-id> --format chat`
- `AT: retry` -> retry the first failed step with `retry <session-id> --format chat`
- `AT: start task, <task>` -> `python "E:\AT FLOW\at.py" --root "E:\AT FLOW" start "<task>" --format chat`
- `AT: start task, <task> --run` -> `python "E:\AT FLOW\at.py" --root "E:\AT FLOW" start "<task>" --run --format chat`

If a command needs `<session-id>` and the user did not provide one, use the
latest AT session from `python "E:\AT FLOW\at.py" --root "E:\AT FLOW" list`. If there is no
session, show the AT control panel and ask for `AT: start task, <task>`.

## Output Rules

- Always show the AT ASCII state machine before any explanation.
- Preserve code blocks produced by `--format chat`.
- Do not replace the ASCII panel with prose.
- Keep Codex/provider as the execution layer, not the flow owner.

<!-- AT_FLOW_TRIGGER_END -->

from __future__ import annotations

from pathlib import Path


BEGIN_MARKER = "<!-- AT_FLOW_TRIGGER_BEGIN -->"
END_MARKER = "<!-- AT_FLOW_TRIGGER_END -->"


def render_codex_trigger_block(target_root: Path, at_command: str = "python -m at_flow") -> str:
    root = str(target_root.resolve())
    return f"""# AT Flow Trigger

{BEGIN_MARKER}

This project has AT Flow enabled.

AT is a conversation-controlled multi-agent runtime. The user-facing interface is
the Codex conversation. The CLI command is only the background runtime.

## Trigger Rules

When the user's message is exactly one of these:

- `AT`
- `AT:`
- `AT：`

do not answer conversationally. Run this command and show its output exactly as
the AT ASCII control panel:

```powershell
{at_command} --root "{root}" panel --format chat
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

- `AT: init` -> `{at_command} --root "{root}" init`
- `AT: status` -> `{at_command} --root "{root}" panel --format chat`
- `AT: list` -> `{at_command} --root "{root}" list --format chat`
- `AT: next` -> run the current session one step with `run <session-id> --one-step --format chat`
- `AT: continue` -> run the current session with `run <session-id> --format chat`
- `AT: retry` -> retry the first failed step with `retry <session-id> --format chat`
- `AT: start task, <task>` -> `{at_command} --root "{root}" start "<task>" --format chat`
- `AT: start task, <task> --run` -> `{at_command} --root "{root}" start "<task>" --run --format chat`

If a command needs `<session-id>` and the user did not provide one, use the
latest AT session from `{at_command} --root "{root}" list`. If there is no
session, show the AT control panel and ask for `AT: start task, <task>`.

## Output Rules

- Always show the AT ASCII state machine before any explanation.
- Preserve code blocks produced by `--format chat`.
- Do not replace the ASCII panel with prose.
- Keep Codex/provider as the execution layer, not the flow owner.

{END_MARKER}
"""


def install_codex_trigger(
    target_root: Path,
    at_entrypoint: Path | None = None,
    at_command: str | None = None,
) -> Path:
    target_root = target_root.resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    agents_path = target_root / "AGENTS.md"
    command = at_command or _at_command_from_entrypoint(at_entrypoint)
    block = render_codex_trigger_block(target_root, command).rstrip() + "\n"

    if agents_path.exists():
        content = agents_path.read_text(encoding="utf-8")
        content = _replace_or_append_block(content, block)
    else:
        content = block
    agents_path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return agents_path


def _at_command_from_entrypoint(at_entrypoint: Path | None) -> str:
    if at_entrypoint is None:
        return "python -m at_flow"
    return f'python "{at_entrypoint.resolve()}"'


def _replace_or_append_block(content: str, block: str) -> str:
    begin = content.find(BEGIN_MARKER)
    end = content.find(END_MARKER)
    if begin != -1 and end != -1 and begin < end:
        start = content.rfind("# AT Flow Trigger", 0, begin)
        if start == -1:
            start = begin
        end += len(END_MARKER)
        return content[:start].rstrip() + "\n\n" + block + "\n" + content[end:].lstrip()
    return content.rstrip() + "\n\n" + block

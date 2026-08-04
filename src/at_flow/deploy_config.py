from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys


CODEX_SANDBOX_FLAG = "--sandbox"


def render_codex_config(api_key: str) -> str:
    return f'''model = "deepseek-v4-flash"
model_provider = "deepseek"
preferred_auth_method = "apikey"
forced_login_method = "api"

[model_providers.deepseek]
name = "deepseek"
base_url = "https://api.deepseek.com/"
wire_api = "responses"
experimental_bearer_token = "{api_key}"
'''


def apply_sandbox(config: dict, sandbox: str) -> tuple[dict, bool]:
    updated = deepcopy(config)
    command = updated.get("providers", {}).get("codex", {}).get("command")
    if not isinstance(command, list) or CODEX_SANDBOX_FLAG not in command:
        return updated, False
    index = command.index(CODEX_SANDBOX_FLAG)
    if index + 1 >= len(command):
        command.append(sandbox)
        return updated, True
    if command[index + 1] == sandbox:
        return updated, False
    command[index + 1] = sandbox
    return updated, True


def write_opencode_config(root: Path) -> dict:
    from .setup import merge_opencode_config

    return merge_opencode_config(None, root)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="at-deploy-config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    codex = subparsers.add_parser("write-codex", help="write codex config.toml")
    codex.add_argument("--key", required=True)
    codex.add_argument("--out", default="/root/.codex/config.toml")

    sandbox = subparsers.add_parser("apply-sandbox", help="set codex --sandbox in at.config.json")
    sandbox.add_argument("sandbox", choices=["workspace-write", "read-only", "ignore"])
    sandbox.add_argument("--config", required=True)

    opencode = subparsers.add_parser("write-opencode", help="write opencode global config")
    opencode.add_argument("--root", required=True)
    opencode.add_argument("--out", default="/root/.config/opencode/opencode.jsonc")

    args = parser.parse_args(argv)
    if args.command == "write-codex":
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_codex_config(args.key), encoding="utf-8")
        print(f"wrote {path}")
        return 0
    if args.command == "apply-sandbox":
        path = Path(args.config)
        config = json.loads(path.read_text(encoding="utf-8"))
        updated, changed = apply_sandbox(config, args.sandbox)
        if changed:
            path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
        print(f"sandbox={args.sandbox} changed={changed}")
        return 0
    if args.command == "write-opencode":
        data = write_opencode_config(Path(args.root))
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())

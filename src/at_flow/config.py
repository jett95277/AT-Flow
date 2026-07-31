from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


CONFIG_NAME = "at.config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "workspace": {
        "shared_dir": ".at/shared",
        "agents_dir": ".at/shared/agents",
        "sessions_dir": ".at/sessions",
        "projects_dir": ".at/projects",
    },
    "pipeline": ["main", "analysis", "code", "test"],
    "providers": {
        "mock": {
            "type": "mock",
        },
        "codex": {
            "type": "process",
            "command": ["codex"],
            "prompt_mode": "stdin",
            "cwd": "workspace",
            "env_policy": "minimal",
            "env_passthrough": [
                "PATH",
                "PATHEXT",
                "SystemRoot",
                "ComSpec",
                "TEMP",
                "TMP",
                "HOME",
                "USERPROFILE",
                "APPDATA",
                "LOCALAPPDATA",
                "LANG",
            ],
            "timeout_seconds": 1800,
        },
        "opencode": {
            "type": "process",
            "command": ["opencode"],
            "prompt_mode": "stdin",
            "cwd": "workspace",
            "env_policy": "minimal",
            "env_passthrough": [
                "PATH",
                "PATHEXT",
                "SystemRoot",
                "ComSpec",
                "TEMP",
                "TMP",
                "HOME",
                "USERPROFILE",
                "APPDATA",
                "LOCALAPPDATA",
                "LANG",
            ],
            "timeout_seconds": 1800,
        },
    },
}


class ConfigError(RuntimeError):
    pass


def find_config(start: Path) -> Path | None:
    current = start.resolve()
    for path in (current, *current.parents):
        candidate = path / CONFIG_NAME
        if candidate.exists():
            return candidate
    return None


def default_config() -> dict[str, Any]:
    return deepcopy(DEFAULT_CONFIG)


def write_default_config(root: Path) -> Path:
    path = root / CONFIG_NAME
    if not path.exists():
        path.write_text(json.dumps(default_config(), indent=2) + "\n", encoding="utf-8")
    return path


def load_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_NAME
    if not path.exists():
        raise ConfigError(f"Missing {CONFIG_NAME}. Run `python .\\at.py init` first.")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return merge_defaults(data)


def merge_defaults(data: dict[str, Any]) -> dict[str, Any]:
    merged = default_config()
    _deep_update(merged, data)
    return merged


def _deep_update(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_MANIFEST = {
    "version": 1,
    "project": {"name": "project"},
    "runtime": {"context_policy": "./policies.yaml"},
    "workflow": {"provider": "superpowers"},
    "knowledge": {"provider": "local"},
    "execution": {"provider": "local"},
    "agents": {
        "analysis": {"provider": "codex"},
        "code": {"provider": "codex"},
        "test": {"provider": "codex"},
    },
}

DEFAULT_POLICIES = {
    "version": 1,
    "roles": {
        "analysis": {
            "read": ["source", "wiki", "project_memory", "analysis_memory"],
            "write": ["short_memory", "feature_memory", "handoff:analysis_to_code"],
        },
        "code": {
            "read": [
                "source",
                "wiki",
                "project_memory",
                "code_memory",
                "handoff:analysis_to_code",
            ],
            "write": ["source", "short_memory", "feature_memory", "handoff:code_to_test"],
        },
        "test": {
            "read": [
                "source",
                "wiki",
                "project_memory",
                "test_memory",
                "handoff:code_to_test",
            ],
            "write": ["test_artifacts", "test_memory", "handoff:test_to_code"],
        },
    },
}


def initialize_workspace(root: Path) -> Path:
    directories = (
        ".agent/runtime/sessions",
        ".agent/runtime/tasks",
        ".agent/runtime/events",
        ".agent/contexts/bundles",
        ".agent/memory/short",
        ".agent/memory/medium",
        ".agent/memory/long",
        ".agent/handoffs",
        ".agent/artifacts",
        ".agent/knowledge/refs",
    )
    for relative in directories:
        (root / relative).mkdir(parents=True, exist_ok=True)
    manifest = root / ".agent/manifest.yaml"
    if not manifest.exists():
        manifest.write_text(
            yaml.safe_dump(DEFAULT_MANIFEST, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    policies = root / ".agent/policies.yaml"
    if not policies.exists():
        policies.write_text(
            yaml.safe_dump(DEFAULT_POLICIES, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    return root / ".agent"


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / ".agent/manifest.yaml"
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_policies(root: Path) -> dict[str, Any]:
    path = root / ".agent/policies.yaml"
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}

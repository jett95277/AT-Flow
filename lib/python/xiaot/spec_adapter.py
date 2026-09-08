"""Spec workflow adapter (M4 skeleton): reuse the open source spec-driven CLI.

xiaot does not implement the spec engine; it drives the external spec-driven
CLI machine surface (--json). Skeleton: availability probe + new-change/status
calls. The spec tool name is internal implementation detail (not surfaced in
xiaot's external docs).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _spec_cli() -> str | None:
    """Locate the spec CLI binary (env override > PATH > known install)."""
    env = os.environ.get("SPEC_CLI")
    if env and Path(env).exists():
        return env
    found = shutil.which("openspec")
    if found:
        return found
    # fallback: fnm-managed install observed on this machine
    known = Path.home() / "AppData/Roaming/fnm/node-versions/v24.14.1/installation/openspec.cmd"
    return str(known) if known.exists() else None


def available() -> bool:
    return _spec_cli() is not None


def _run(args: list[str], cwd: str | None = None) -> dict[str, Any]:
    cli = _spec_cli()
    if not cli:
        return {"ok": False, "error": "spec workflow CLI unavailable"}
    try:
        proc = subprocess.run([cli, *args], capture_output=True, text=True,
                              timeout=60, encoding="utf-8", errors="replace",
                              cwd=cwd)
    except Exception as exc:  # noqa: BLE001 - surface clear error
        return {"ok": False, "error": f"spec CLI call failed: {exc}"}
    return {"ok": proc.returncode == 0, "rc": proc.returncode,
            "stdout": proc.stdout[:2000], "stderr": proc.stderr[:500]}


def init_workspace(path: str | Path) -> dict[str, Any]:
    """Create a spec workspace structure (structure only; no agent injection)."""
    return _run(["init", str(path), "--tools", "none"])


def new_change(name: str, cwd: str | Path | None = None) -> dict[str, Any]:
    """Scaffold a new spec work unit inside a workspace (cwd)."""
    return _run(["new", "change", name], cwd=str(cwd) if cwd else None)


def status_json(change: str, cwd: str | Path | None = None) -> dict[str, Any]:
    """Read work-unit status machine surface (--json) inside a workspace."""
    return _run(["status", "--change", change, "--json"],
                cwd=str(cwd) if cwd else None)

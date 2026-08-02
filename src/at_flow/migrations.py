from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil

from .config import CONFIG_NAME


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentLayoutMigration:
    source: str
    target: str
    status: str
    moved_files: list[str]


def migrate_agent_layout(root: Path, *, apply: bool) -> AgentLayoutMigration:
    workspace_root = root.resolve()
    config_path = workspace_root / CONFIG_NAME
    if not config_path.is_file():
        raise MigrationError(f"Missing {CONFIG_NAME}: {config_path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    workspace_config = config.get("workspace")
    if not isinstance(workspace_config, dict):
        raise MigrationError("Invalid workspace configuration")

    source = (workspace_root / ".at" / "shared" / "agents").resolve()
    target = (workspace_root / ".at" / "agents").resolve()
    configured = str(workspace_config.get("agents_dir") or "")
    moved_files = _relative_files(source)

    if configured == ".at/agents" and not source.exists():
        return AgentLayoutMigration(str(source), str(target), "not_needed", [])
    if configured != ".at/shared/agents":
        raise MigrationError(f"Agent layout is not the legacy default: {configured or '(empty)'}")
    if not source.is_dir():
        raise MigrationError(f"Legacy Agent directory does not exist: {source}")
    if target.exists() and any(target.iterdir()):
        raise MigrationError(f"Migration target is not empty: {target}")
    if not apply:
        return AgentLayoutMigration(str(source), str(target), "preview", moved_files)

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.rmdir()
    shutil.move(str(source), str(target))
    workspace_config["agents_dir"] = ".at/agents"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return AgentLayoutMigration(str(source), str(target), "migrated", moved_files)


def _relative_files(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())

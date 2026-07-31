from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .codex_trigger import install_codex_trigger
from .config import ConfigError
from .engine import Runner
from .inspectors import (
    doctor_checks,
    render_audit_summary,
    render_doctor_checks,
    render_trace_summary,
    session_artifact_text,
    session_audit_summary,
    session_trace_summary,
)
from .models import SessionState
from .render import (
    render_chat_panel,
    render_chat_session,
    render_chat_session_table,
    render_session,
    render_session_row,
)
from .workspace import ATWorkspace, WorkspaceError


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, WorkspaceError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="at", description="AT Flow multi-agent CLI")
    parser.add_argument("--root", default=".", help="AT workspace root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize an AT workspace")
    init_parser.set_defaults(func=cmd_init)

    enable_parser = subparsers.add_parser("enable", help="initialize AT and install Codex trigger")
    enable_parser.add_argument("--target", default=".", help="target project root")
    enable_parser.add_argument("--at-command", default=None, help="command used by AGENTS.md to run AT")
    enable_parser.set_defaults(func=cmd_enable)

    panel_parser = subparsers.add_parser("panel", help="show the AT conversation control panel")
    panel_parser.add_argument("--format", choices=["text", "chat"], default="text", help="output format")
    panel_parser.set_defaults(func=cmd_panel)

    trigger_parser = subparsers.add_parser("install-codex-trigger", help="install AT trigger rules into AGENTS.md")
    trigger_parser.add_argument("--target", default=".", help="target project root")
    trigger_parser.add_argument("--at-entrypoint", default=None, help="path to at.py")
    trigger_parser.add_argument("--at-command", default=None, help="command used by AGENTS.md to run AT")
    trigger_parser.set_defaults(func=cmd_install_codex_trigger)

    start_parser = subparsers.add_parser("start", help="create a new AT session")
    start_parser.add_argument("task", help="task for the agent team")
    start_parser.add_argument("--project", default=None, help="shared project path")
    start_parser.add_argument("--provider", default="mock", help="provider name from at.config.json")
    start_parser.add_argument("--session-id", default=None, help="explicit session id")
    start_parser.add_argument("--run", action="store_true", help="run the session immediately")
    start_parser.add_argument("--format", choices=["text", "chat"], default="text", help="output format")
    start_parser.set_defaults(func=cmd_start)

    run_parser = subparsers.add_parser("run", help="advance an existing session")
    run_parser.add_argument("session_id", help="session id")
    run_parser.add_argument("--provider", default=None, help="override provider for this run")
    run_parser.add_argument("--one-step", action="store_true", help="run only the next queued step")
    run_parser.add_argument("--format", choices=["text", "chat"], default="text", help="output format")
    run_parser.set_defaults(func=cmd_run)

    retry_parser = subparsers.add_parser("retry", help="retry the first failed step in a session")
    retry_parser.add_argument("session_id", help="session id")
    retry_parser.add_argument("--one-step", action="store_true", help="retry only the failed step")
    retry_parser.add_argument("--format", choices=["text", "chat"], default="text", help="output format")
    retry_parser.set_defaults(func=cmd_retry)

    status_parser = subparsers.add_parser("status", help="show one session")
    status_parser.add_argument("session_id", help="session id")
    status_parser.add_argument("--format", choices=["text", "chat"], default="text", help="output format")
    status_parser.set_defaults(func=cmd_status)

    list_parser = subparsers.add_parser("list", help="list sessions")
    list_parser.add_argument("--format", choices=["text", "chat"], default="text", help="output format")
    list_parser.set_defaults(func=cmd_list)

    trace_parser = subparsers.add_parser("trace", help="show session trace events")
    trace_parser.add_argument("session_id", help="session id")
    trace_parser.set_defaults(func=cmd_trace)

    audit_parser = subparsers.add_parser("audit", help="show session audit reports")
    audit_parser.add_argument("session_id", help="session id")
    audit_parser.set_defaults(func=cmd_audit)

    artifact_parser = subparsers.add_parser("artifact", help="show an agent artifact or failure")
    artifact_parser.add_argument("session_id", help="session id")
    artifact_parser.add_argument("agent", help="agent name")
    artifact_parser.set_defaults(func=cmd_artifact)

    doctor_parser = subparsers.add_parser("doctor", help="check AT workspace health")
    doctor_parser.set_defaults(func=cmd_doctor)

    return parser


def cmd_init(args: argparse.Namespace) -> int:
    workspace = ATWorkspace.init(Path(args.root))
    print(f"initialized: {workspace.root}")
    print(f"config: {workspace.root / 'at.config.json'}")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    target = Path(args.target)
    workspace = ATWorkspace.init(target)
    agents_path = install_codex_trigger(workspace.root, at_command=args.at_command)
    print(f"enabled: {workspace.root}")
    print(f"config: {workspace.root / 'at.config.json'}")
    print(f"trigger: {agents_path}")
    print("next: restart Codex in the target project and type AT")
    return 0


def cmd_panel(args: argparse.Namespace) -> int:
    workspace = ATWorkspace.require(Path(args.root))
    sessions = workspace.list_sessions()
    if args.format == "chat":
        print(render_chat_panel(sessions))
        return 0
    if not sessions:
        print("AT ready")
        print("next: start a task")
        return 0
    latest = sessions[-1]
    print(render_session(latest))
    return 0


def cmd_install_codex_trigger(args: argparse.Namespace) -> int:
    at_entrypoint = Path(args.at_entrypoint).resolve() if args.at_entrypoint else None
    agents_path = install_codex_trigger(Path(args.target), at_entrypoint, at_command=args.at_command)
    print(f"installed: {agents_path}")
    print("restart Codex in the target project so it reads AGENTS.md")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    workspace = ATWorkspace.require(Path(args.root))
    project = Path(args.project).resolve() if args.project else workspace.projects_root / "default"
    pipeline = workspace.config.get("pipeline", ["main", "analysis", "code", "test"])
    session = SessionState.new(
        task=args.task,
        project_path=project,
        provider=args.provider,
        pipeline=pipeline,
        session_id=args.session_id,
    )
    workspace.create_session(session)
    renderer = _renderer(args.format)
    print(renderer(session))
    if args.run:
        final_state = Runner(workspace, renderer=renderer).run(session.id)
        print(renderer(final_state))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    workspace = ATWorkspace.require(Path(args.root))
    renderer = _renderer(args.format)
    session = Runner(workspace, renderer=renderer).run(
        args.session_id,
        provider_name=args.provider,
        one_step=args.one_step,
    )
    print(renderer(session))
    return 0 if not session.has_failed() else 1


def cmd_retry(args: argparse.Namespace) -> int:
    workspace = ATWorkspace.require(Path(args.root))
    renderer = _renderer(args.format)
    session = Runner(workspace, renderer=renderer).retry(args.session_id, one_step=args.one_step)
    print(renderer(session))
    return 0 if not session.has_failed() else 1


def cmd_status(args: argparse.Namespace) -> int:
    workspace = ATWorkspace.require(Path(args.root))
    print(_renderer(args.format)(workspace.load_session(args.session_id)))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    workspace = ATWorkspace.require(Path(args.root))
    sessions = workspace.list_sessions()
    if not sessions:
        print("no sessions")
        return 0
    if args.format == "chat":
        print(render_chat_session_table(sessions))
        return 0
    for session in sessions:
        print(render_session_row(session))
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    workspace = ATWorkspace.require(Path(args.root))
    workspace.load_session(args.session_id)
    print(render_trace_summary(session_trace_summary(workspace, args.session_id)))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    workspace = ATWorkspace.require(Path(args.root))
    workspace.load_session(args.session_id)
    print(render_audit_summary(session_audit_summary(workspace, args.session_id)))
    return 0


def cmd_artifact(args: argparse.Namespace) -> int:
    workspace = ATWorkspace.require(Path(args.root))
    workspace.load_session(args.session_id)
    print(session_artifact_text(workspace, args.session_id, args.agent))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    workspace = ATWorkspace.require(Path(args.root))
    checks = doctor_checks(workspace)
    print(render_doctor_checks(checks))
    return 0 if all(ok for _, ok, _ in checks) else 1


def _renderer(format_name: str):
    if format_name == "chat":
        return render_chat_session
    return render_session

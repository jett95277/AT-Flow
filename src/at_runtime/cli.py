from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


if sys.platform == "win32":
    # Windows 编码适配：直接显示时 conhost 按系统代码页（936/GBK）解码，
    # 管道/重定向时 PowerShell 按 [Console]::OutputEncoding（UTF-8）解码。
    encoding = "utf-8" if not sys.stdout.isatty() else "cp936"
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding=encoding)
        except (AttributeError, ValueError):
            pass

from at_runtime.context import build_context
from at_runtime.eval import run_minimal_eval
from at_runtime.handoff import get_handoff
from at_runtime.memory import (
    archive_memory,
    discard_memory,
    promote_memory,
    read_memory,
    write_memory_structured,
)
from at_runtime.runner import run_doctor, run_task_flow
from at_runtime.timeline import create_checkpoint, list_checkpoints, rollback_memory
from at_runtime.view import render_memory_tree
from at_runtime.workspace import initialize_workspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="at", description="AT Context Runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="initialize .agent workspace")
    memory_parser = subparsers.add_parser("memory", help="inspect memory")
    memory_sub = memory_parser.add_subparsers(dest="memory_command", required=True)
    inspect = memory_sub.add_parser("inspect", help="show memory entries for a uri")
    inspect.add_argument("uri", help="memory://<scope>/<name>/<tier>")
    write = memory_sub.add_parser("write", help="write structured memory (three fields)")
    write.add_argument("uri")
    write.add_argument("--conclusion", default="", help="conclusion text")
    write.add_argument("--constraint", action="append", default=[],
                       help="constraint (repeatable)")
    write.add_argument("--unresolved", action="append", default=[],
                       help="unresolved item (repeatable)")
    write.add_argument("--task", default=None, help="task id for promote scope migration")
    write.add_argument("--project", default=None, help="project name for promote scope migration")
    get = memory_sub.add_parser("get", help="read structured memory entries (for agents)")
    get.add_argument("uri")
    view = memory_sub.add_parser("view", help="show memory tree")
    view.add_argument("--all", action="store_true",
                      help="include archived/deprecated and expand short")
    promote = memory_sub.add_parser("promote", help="promote memory entry")
    promote.add_argument("uri")
    promote.add_argument("--to", choices=["medium", "long"], default=None,
                         help="move to another tier (migrates scope)")
    archive = memory_sub.add_parser("archive", help="archive memory entry")
    archive.add_argument("uri")
    discard = memory_sub.add_parser("discard", help="discard memory entry")
    discard.add_argument("uri")
    checkpoint = memory_sub.add_parser("checkpoint", help="create memory checkpoint")
    checkpoint.add_argument("label", help="checkpoint label")
    memory_sub.add_parser("timeline", help="list checkpoints")
    rollback = memory_sub.add_parser("rollback", help="rollback memory to checkpoint")
    rollback.add_argument("node", help="checkpoint id (from timeline)")
    context_parser = subparsers.add_parser("context", help="inspect context")
    context_sub = context_parser.add_subparsers(dest="context_command", required=True)
    context_inspect = context_sub.add_parser("inspect", help="build and show context bundle")
    context_inspect.add_argument("session_id", help="session id")
    handoff_parser = subparsers.add_parser("handoff", help="inspect handoff")
    handoff_sub = handoff_parser.add_subparsers(dest="handoff_command", required=True)
    handoff_inspect = handoff_sub.add_parser("inspect", help="show a handoff")
    handoff_inspect.add_argument("handoff_id", help="handoff id")
    task_parser = subparsers.add_parser("task", help="run a task flow")
    task_sub = task_parser.add_subparsers(dest="task_command", required=True)
    task_run = task_sub.add_parser("run", help="run analysis -> code -> test flow")
    task_run.add_argument("task_id", help="task id")
    task_run.add_argument("goal", help="task goal")
    task_run.add_argument(
        "--provider", default="mock", choices=["mock", "codex"], help="execution provider"
    )
    task_run.add_argument(
        "--constraint", action="append", default=[], help="constraint (repeatable)"
    )
    eval_parser = subparsers.add_parser("eval", help="run minimal baseline vs AT eval")
    eval_parser.add_argument("demo_task", help="demo task goal text")
    eval_parser.add_argument(
        "--provider", default="mock", choices=["mock", "codex"], help="execution provider"
    )
    subparsers.add_parser("doctor", help="check .agent workspace health")
    args = parser.parse_args(argv)
    if args.command == "init":
        agent_dir = initialize_workspace(Path.cwd())
        print(f"at init: created {agent_dir}")
        return 0
    if args.command == "memory":
        root = Path.cwd()
        if args.memory_command == "inspect":
            entries = read_memory(root, args.uri)
            print(json.dumps(entries, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "write":
            source = {}
            if args.task:
                source["task"] = args.task
            if args.project:
                source["project"] = args.project
            result = write_memory_structured(
                root,
                args.uri,
                conclusion=args.conclusion,
                constraints=args.constraint,
                unresolved=args.unresolved,
                source=source or None,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "get":
            entries = read_memory(root, args.uri)
            print(json.dumps(entries, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "view":
            print(render_memory_tree(root, include_all=args.all))
            return 0
        if args.memory_command == "promote":
            result = promote_memory(root, args.uri, to_tier=args.to)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "archive":
            result = archive_memory(root, args.uri)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "discard":
            result = discard_memory(root, args.uri)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "checkpoint":
            result = create_checkpoint(root, args.label)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "timeline":
            nodes = list_checkpoints(root)
            print(json.dumps(nodes, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "rollback":
            result = rollback_memory(root, args.node)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
    if args.command == "context":
        if args.context_command == "inspect":
            bundle = build_context(Path.cwd(), args.session_id, explicit_refs={})
            print(json.dumps(bundle, ensure_ascii=False, indent=2))
            return 0
    if args.command == "handoff":
        if args.handoff_command == "inspect":
            handoff = get_handoff(Path.cwd(), args.handoff_id)
            print(json.dumps(handoff, ensure_ascii=False, indent=2))
            return 0
    if args.command == "task":
        if args.task_command == "run":
            steps = run_task_flow(
                Path.cwd(),
                args.task_id,
                args.goal,
                {"constraints": args.constraint},
                provider=args.provider,
            )
            print(json.dumps(steps, ensure_ascii=False, indent=2))
            return 0
    if args.command == "eval":
        result = run_minimal_eval(
            Path.cwd(),
            args.demo_task,
            provider=args.provider,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "doctor":
        report = run_doctor(Path.cwd())
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

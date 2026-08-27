"""xiaot 记忆命令（薄 CLI）：只暴露 init + memory 治理子命令。

复用 AT 记忆引擎的存储/治理/结算语义（`root = Path.cwd()` + `.agent`），
不依赖 at 运行时与编排模块。完整命令面见 xiaot-env.ps1 导出的 $Xiaot.MemoryCmd。
"""

from __future__ import annotations

import argparse
from datetime import datetime
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

from xiaot_memory.memory import (
    archive_memory,
    discard_memory,
    promote_memory,
    read_memory,
)
from xiaot_memory.memory_context import build_memory_context
from xiaot_memory.memory_events import list_actions
from xiaot_memory.memory_policy import (
    request_conflict,
    request_promote,
    request_supersede,
    request_verify,
    write_entry,
)
from xiaot_memory.memory_settle import apply_confirmed, settle_task
from xiaot_memory.timeline import create_checkpoint, list_checkpoints, rollback_memory
from xiaot_memory.view import render_memory_export, render_memory_stats, render_memory_tree
from xiaot_memory.workspace import initialize_workspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xiaot-memory", description="xiaot memory command")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="initialize .agent workspace")
    memory_parser = subparsers.add_parser("memory", help="governed memory")
    memory_sub = memory_parser.add_subparsers(dest="memory_command", required=True)
    get = memory_sub.add_parser("get", help="read structured memory entries (for agents)")
    get.add_argument("uri")
    view = memory_sub.add_parser("view", help="show memory tree")
    view.add_argument("--all", action="store_true",
                      help="include archived/deprecated and expand short")
    promote = memory_sub.add_parser("promote", help="promote memory entry")
    promote.add_argument("uri")
    promote.add_argument("--to", choices=["medium", "long"], default=None,
                         help="move to another tier (migrates scope)")
    promote.add_argument("--index", type=int, default=-1,
                         help="entry index within uri (default: newest)")
    promote.add_argument("--all", action="store_true",
                         help="apply to all entries of the uri")
    promote.add_argument("--confirmed", action="store_true",
                         help="user-confirmed（严格晋升必需）")
    promote.add_argument("--evidence", action="append", default=[],
                         help="evidence (repeatable)")
    promote.add_argument("--distilled", default=None,
                         help="重新提炼文本（严格晋升必需，禁止复制原文）")
    archive = memory_sub.add_parser("archive", help="archive memory entry")
    archive.add_argument("uri")
    archive.add_argument("--index", type=int, default=-1,
                         help="entry index within uri (default: newest)")
    archive.add_argument("--all", action="store_true",
                         help="apply to all entries of the uri")
    discard = memory_sub.add_parser("discard", help="discard memory entry")
    discard.add_argument("uri")
    discard.add_argument("--index", type=int, default=-1,
                         help="entry index within uri (default: newest)")
    discard.add_argument("--all", action="store_true",
                         help="apply to all entries of the uri")
    checkpoint = memory_sub.add_parser("checkpoint", help="create memory checkpoint")
    checkpoint.add_argument("label", help="checkpoint label")
    memory_sub.add_parser("timeline", help="list checkpoints")
    rollback = memory_sub.add_parser("rollback", help="rollback memory to checkpoint")
    rollback.add_argument("node", help="checkpoint id (from timeline)")
    export = memory_sub.add_parser("export", help="export memory as markdown report")
    export.add_argument("--out", default=None, help="output file path")
    export.add_argument("--stdout", action="store_true", help="print report to stdout")
    export.add_argument("--all", action="store_true",
                        help="include archived/deprecated entries")
    stats = memory_sub.add_parser("stats", help="show memory statistics")
    stats.add_argument("--all", action="store_true",
                       help="include archived/deprecated entries")
    add = memory_sub.add_parser("add", help="admit a governed memory entry")
    add.add_argument("uri")
    add.add_argument("--conclusion", default="", help="content text")
    add.add_argument("--kind", default="conclusion",
                     choices=["conclusion", "observation", "risk", "unresolved",
                              "constraint", "preference", "rule"])
    add.add_argument("--constraint", action="append", default=[],
                     help="constraint (repeatable)")
    add.add_argument("--unresolved", action="append", default=[],
                     help="unresolved item (repeatable)")
    add.add_argument("--task", default=None, help="task id (required for short)")
    add.add_argument("--project", default=None, help="project name")
    add.add_argument("--confirmed", action="store_true",
                     help="user-confirmed (medium constraint / long preference)")
    add.add_argument("--evidence", action="append", default=[],
                     help="evidence (repeatable)")
    add.add_argument("--supersedes", default=None, help="uri this entry replaces")
    add.add_argument("--supersedes-index", type=int, default=-1)
    verify = memory_sub.add_parser("verify", help="verify a memory entry with evidence")
    verify.add_argument("uri")
    verify.add_argument("--index", type=int, default=-1)
    verify.add_argument("--evidence", action="append", default=[],
                        help="evidence (repeatable)")
    verify.add_argument("--confirmed", action="store_true",
                        help="user-confirmed（legacy 补证）")
    settle = memory_sub.add_parser("settle", help="settle a task's short memory")
    settle.add_argument("task_id")
    settle.add_argument("--apply", action="store_true",
                        help="auto-archive pure-process records")
    settle.add_argument("--incomplete", action="store_true",
                        help="task not completed: skip process archival")
    settle.add_argument("--confirmed", action="store_true",
                        help="apply confirmed discard/conflict ids")
    settle.add_argument("--discard", action="append", default=[],
                        help="entry id to discard (needs --confirmed)")
    settle.add_argument("--conflict", action="append", default=[],
                        help="entry id to mark conflicted (needs --confirmed)")
    supersede = memory_sub.add_parser("supersede", help="supersede a memory entry")
    supersede.add_argument("uri")
    supersede.add_argument("--index", type=int, default=-1)
    supersede.add_argument("--replaces", required=True, help="uri being replaced")
    supersede.add_argument("--replaces-index", type=int, default=-1)
    supersede.add_argument("--confirmed", action="store_true", help="required")
    conflict = memory_sub.add_parser("conflict", help="mark a memory entry conflicted")
    conflict.add_argument("uri")
    conflict.add_argument("--index", type=int, default=-1)
    conflict.add_argument("--confirmed", action="store_true", help="required")
    mem_context = memory_sub.add_parser("context", help="show governed memory context")
    mem_context.add_argument("uri")
    events = memory_sub.add_parser("events", help="list governance audit events")
    events.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _dispatch(args) -> int:
    if args.command == "init":
        agent_dir = initialize_workspace(Path.cwd())
        print(f"xiaot-memory init: created {agent_dir}")
        return 0
    if args.command == "memory":
        root = Path.cwd()
        if args.memory_command == "add":
            source = {}
            if args.task:
                source["task"] = args.task
            if args.project:
                source["project"] = args.project
            result = write_entry(
                root, args.uri, args.conclusion, source or None,
                kind=args.kind, task_id=args.task, evidence=args.evidence,
                confirmed=args.confirmed, constraints=args.constraint,
                unresolved=args.unresolved,
                supersedes_uri=args.supersedes,
                supersedes_index=args.supersedes_index,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "verify":
            result = request_verify(
                root, args.uri, index=args.index,
                evidence=args.evidence or None, confirmed=args.confirmed,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "settle":
            if args.confirmed:
                result = apply_confirmed(
                    root, args.task_id, discard_ids=args.discard,
                    conflict_ids=args.conflict,
                )
            else:
                result = settle_task(
                    root, args.task_id, dry_run=not args.apply,
                    task_completed=not args.incomplete,
                )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "supersede":
            result = request_supersede(
                root, args.uri, index=args.index,
                replaces_uri=args.replaces, replaces_index=args.replaces_index,
                confirmed=args.confirmed,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "conflict":
            result = request_conflict(
                root, args.uri, index=args.index, confirmed=args.confirmed,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "context":
            ctx = build_memory_context(root, [args.uri])
            print(json.dumps(ctx, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "events":
            audit = list_actions(root, limit=args.limit)
            print(json.dumps(audit, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "get":
            entries = read_memory(root, args.uri)
            print(json.dumps(entries, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "view":
            print(render_memory_tree(root, include_all=args.all))
            return 0
        if args.memory_command in ("promote", "archive", "discard"):
            if args.index != -1 and args.all:
                print("error: --index and --all are mutually exclusive", file=sys.stderr)
                return 1
        if args.memory_command == "promote":
            # 带严格标志（--confirmed/--evidence/--distilled）走治理层；否则 legacy 状态提升。
            if args.to and (args.confirmed or args.evidence or args.distilled):
                result = request_promote(
                    root, args.uri, args.to, index=args.index, all_=args.all,
                    confirmed=args.confirmed, evidence=args.evidence or None,
                    distilled=args.distilled,
                )
            else:
                result = promote_memory(root, args.uri, to_tier=args.to,
                                        index=args.index, all_=args.all)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "archive":
            result = archive_memory(root, args.uri, index=args.index, all_=args.all)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.memory_command == "discard":
            result = discard_memory(root, args.uri, index=args.index, all_=args.all)
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
        if args.memory_command == "export":
            report = render_memory_export(root, include_all=args.all)
            if args.stdout:
                print(report)
                return 0
            out_dir = root / ".agent/export"
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%dT%H%M%S")
            out_path = Path(args.out) if args.out else out_dir / f"memory-{ts}.md"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(report, encoding="utf-8")
            print(f"exported: {out_path}")
            return 0
        if args.memory_command == "stats":
            report = render_memory_stats(root, include_all=args.all)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

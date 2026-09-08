"""xiaot CLI (M1): orchestration command entry with JSON machine surface.

Boundary: CLI parses args -> dispatches an orchestration command -> prints
machine-readable JSON. It does not touch memory/skill/spec internals or the
executing agent; the calling agent performs execution from the returned
context fragment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="xiaot", description="xiaot orchestration CLI (M1)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_task = sub.add_parser("task", help="start/resume a task closed loop")
    p_task.add_argument("prompt")
    p_task.add_argument("--project", default=None)
    p_task.add_argument("--session", default=None)
    p_task.add_argument("--resume", default=None)

    p_ret = sub.add_parser("retrieve", help="inject task-relevant memory")
    p_ret.add_argument("prompt")
    p_ret.add_argument("--project", default=None)
    p_ret.add_argument("--session", default=None)

    p_plan = sub.add_parser("plan", help="produce and persist plan document")
    p_plan.add_argument("prompt")
    p_plan.add_argument("--project", default=None)
    p_plan.add_argument("--steps", action="append", default=None)
    p_plan.add_argument("--acceptance", default=None)

    p_set = sub.add_parser("settle", help="end-of-task settle suggestions")
    p_set.add_argument("task_id")
    p_set.add_argument("--status", default="success")
    p_set.add_argument("--output", default="")
    p_set.add_argument("--text", action="append", default=None,
                       help="candidate conclusion text (repeatable)")

    p_ck = sub.add_parser("checkpoint", help="snapshot task workspace + memory")
    p_ck.add_argument("task_id")
    p_ck.add_argument("--label", default=None)

    sub.add_parser("timeline", help="list timeline nodes")
    p_rb = sub.add_parser("rollback", help="restore task workspace from a node")
    p_rb.add_argument("node_id")

    p_inj = sub.add_parser("inject", help="inject orchestration commands/skill into agent dir")
    p_inj.add_argument("--agent", default="opencode", help="agent config dir name")
    p_inj.add_argument("--dir", default=None, help="target project root (default resolved root)")

    args = parser.parse_args(argv)
    from xiaot import commands

    if args.cmd == "task":
        result = commands.task(args.prompt, project=args.project,
                               session=args.session, resume=args.resume)
    elif args.cmd == "retrieve":
        result = commands.retrieve(args.prompt, project=args.project,
                                   session=args.session)
    elif args.cmd == "plan":
        result = commands.plan(args.prompt, project=args.project,
                               steps=args.steps, acceptance=args.acceptance)
    elif args.cmd == "settle":
        candidates = [{"text": t} for t in args.text] if args.text else None
        result = commands.settle(args.task_id, status=args.status,
                                 output=args.output, candidates=candidates)
    elif args.cmd == "checkpoint":
        from xiaot import timeline
        result = timeline.checkpoint(commands._resolve_root(), args.task_id,
                                     label=args.label)
    elif args.cmd == "timeline":
        from xiaot import timeline
        result = {"nodes": timeline.list_nodes(commands._resolve_root())}
    elif args.cmd == "rollback":
        from xiaot import timeline
        result = timeline.rollback(commands._resolve_root(), args.node_id)
    elif args.cmd == "inject":
        from xiaot import inject
        target = Path(args.dir) if args.dir else commands._resolve_root()
        result = inject.generate(target, agent=args.agent)
    else:
        result = {"ok": False, "error": f"unknown command {args.cmd}"}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())

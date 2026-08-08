from __future__ import annotations

import argparse
import json
from pathlib import Path

from at_runtime.context import build_context
from at_runtime.eval import run_minimal_eval
from at_runtime.handoff import get_handoff
from at_runtime.memory import read_memory
from at_runtime.runner import run_doctor, run_task_flow
from at_runtime.workspace import initialize_workspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="at", description="AT Context Runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="initialize .agent workspace")
    memory_parser = subparsers.add_parser("memory", help="inspect memory")
    memory_sub = memory_parser.add_subparsers(dest="memory_command", required=True)
    inspect = memory_sub.add_parser("inspect", help="show memory entries for a uri")
    inspect.add_argument("uri", help="memory://<scope>/<name>/<tier>")
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
        if args.memory_command == "inspect":
            entries = read_memory(Path.cwd(), args.uri)
            print(json.dumps(entries, ensure_ascii=False, indent=2))
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

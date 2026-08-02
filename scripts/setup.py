from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow import setup as at_setup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="at-setup", description="AT Flow one-click setup")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check", help="read-only environment check")

    install = subparsers.add_parser("install", help="install dependencies and configure workspace")
    install.add_argument("--skip-build", action="store_true", help="skip npm run build")
    install.add_argument("--skip-frontend", action="store_true", help="skip npm ci")

    start = subparsers.add_parser("start", help="start backend and frontend servers")
    start.add_argument("--backend-port", type=int, default=8000)
    start.add_argument("--frontend-port", type=int, default=3000)

    doctor = subparsers.add_parser("doctor", help="run health checks")
    doctor.add_argument("--backend-port", type=int, default=8000)
    doctor.add_argument("--frontend-port", type=int, default=3000)

    subparsers.add_parser("all", help="check, install, then doctor")

    args = parser.parse_args(argv)
    root = ROOT

    if args.command == "check":
        return _print_report(at_setup.environment_report(root))
    if args.command == "install":
        at_setup.ensure_python_deps(root)
        if not args.skip_frontend:
            at_setup.ensure_frontend_deps(root)
        if not args.skip_build:
            at_setup.ensure_build(root)
        at_setup.ensure_workspace(root)
        at_setup.ensure_codex_trigger(root)
        at_setup.ensure_at_package(root)
        for change in at_setup.ensure_provider_config(root):
            print(f"fixed: {change}")
        print(f"opencode config: {at_setup.ensure_opencode_global_config(root)}")
        return _print_report(at_setup.environment_report(root), fail_on_error=True)
    if args.command == "start":
        return at_setup.start_servers(root, args.backend_port, args.frontend_port)
    if args.command == "doctor":
        return at_setup.run_doctor(root, args.backend_port, args.frontend_port)
    if args.command == "all":
        report = at_setup.environment_report(root)
        _print_report(report)
        if any(item.status == "ERROR" for item in report):
            print("blocking errors found; fix prerequisites before install", file=sys.stderr)
            return 1
        at_setup.ensure_python_deps(root)
        at_setup.ensure_frontend_deps(root)
        at_setup.ensure_build(root)
        at_setup.ensure_workspace(root)
        at_setup.ensure_codex_trigger(root)
        at_setup.ensure_at_package(root)
        for change in at_setup.ensure_provider_config(root):
            print(f"fixed: {change}")
        at_setup.ensure_opencode_global_config(root)
        return at_setup.run_doctor(root, args.backend_port, args.frontend_port)
    parser.error(f"unknown command: {args.command}")
    return 2


def _print_report(report: list, fail_on_error: bool = False) -> int:
    failed = 0
    for item in report:
        marker = {"OK": "OK ", "FIXABLE": "FIX", "MISSING": "MISS", "ERROR": "ERR"}.get(item.status, "???")
        if item.status in {"MISSING", "ERROR", "FIXABLE"}:
            failed += 1
        print(f"[{marker}] {item.name}: {item.detail}")
    if fail_on_error and failed:
        print(f"{failed} item(s) need attention", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

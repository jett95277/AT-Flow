from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser


REQUIRED_PYTHON_PACKAGES = ("fastapi", "uvicorn", "httpx")

CODEX_EXEC_ARGS = [
    "exec",
    "--skip-git-repo-check",
    "--sandbox",
    "workspace-write",
    "--ephemeral",
    "--color",
    "never",
    "-",
]


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


def resolve_npm() -> str:
    return "npm.cmd" if sys.platform.startswith("win") else "npm"


def opencode_config_path(home: Path | None = None) -> Path:
    home = home or Path.home()
    return home / ".config" / "opencode" / "opencode.jsonc"


def environment_report(root: Path) -> list[CheckResult]:
    root = root.resolve()
    results: list[CheckResult] = [
        _check_python_packages(),
        _check_command("node", shutil.which("node")),
        _check_command("npm", shutil.which(resolve_npm())),
        _check_command("codex", shutil.which("codex")),
        _check_command("opencode", shutil.which("opencode")),
        _check_at_workspace(root),
        _check_agents_trigger(root),
        _check_provider_commands(root),
        _check_opencode_global_config(root),
    ]
    return results


def _check_python_packages() -> CheckResult:
    missing = [name for name in REQUIRED_PYTHON_PACKAGES if importlib.util.find_spec(name) is None]
    if missing:
        return CheckResult("python_deps", "MISSING", f"missing: {', '.join(missing)}")
    return CheckResult("python_deps", "OK", "fastapi/uvicorn/httpx importable")


def _check_command(name: str, resolved: str | None) -> CheckResult:
    if resolved:
        return CheckResult(name, "OK", f"command found: {resolved}")
    return CheckResult(name, "MISSING", f"{name} not found in PATH")


def _check_at_workspace(root: Path) -> CheckResult:
    if (root / "at.config.json").exists():
        return CheckResult("at_workspace", "OK", "at.config.json present")
    return CheckResult(
        "at_workspace",
        "MISSING",
        "run `python scripts/setup.py install` or `python at.py init`",
    )


def _check_agents_trigger(root: Path) -> CheckResult:
    agents_path = root / "AGENTS.md"
    if agents_path.exists() and "AT_FLOW_TRIGGER_BEGIN" in agents_path.read_text(encoding="utf-8"):
        return CheckResult("codex_trigger", "OK", "AGENTS.md contains AT trigger block")
    return CheckResult("codex_trigger", "MISSING", "AGENTS.md trigger block not installed")


def _check_provider_commands(root: Path) -> CheckResult:
    config_path = root / "at.config.json"
    if not config_path.exists():
        return CheckResult("provider_commands", "MISSING", "at.config.json missing")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return CheckResult("provider_commands", "ERROR", f"at.config.json not readable/parseable: {exc}")
    providers = config.get("providers", {})
    if not isinstance(providers, dict):
        return CheckResult("provider_commands", "ERROR", "at.config.json providers is not an object")
    codex = list(providers.get("codex", {}).get("command") or [])
    opencode = list(providers.get("opencode", {}).get("command") or [])
    problems = []
    if codex and "exec" not in codex:
        problems.append("codex command is not non-interactive (missing `exec`)")
    if opencode and (len(opencode) < 2 or opencode[1] != "run"):
        problems.append("opencode command is not non-interactive (missing `run`)")
    if problems:
        return CheckResult("provider_commands", "FIXABLE", "; ".join(problems))
    return CheckResult("provider_commands", "OK", "codex/opencode commands are non-interactive")


def _check_opencode_global_config(root: Path) -> CheckResult:
    path = opencode_config_path()
    try:
        exists = path.exists()
    except OSError as exc:
        return CheckResult("opencode_global_config", "ERROR", f"cannot access {path}: {exc}")
    if not exists:
        return CheckResult("opencode_global_config", "MISSING", f"{path} does not exist")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return CheckResult("opencode_global_config", "ERROR", f"{path} not parseable: {exc}")
    permission = data.get("permission", {})
    if not isinstance(permission, dict):
        return CheckResult("opencode_global_config", "ERROR", "permission is not an object")
    rules = permission.get("external_directory", {})
    if not isinstance(rules, dict):
        return CheckResult("opencode_global_config", "ERROR", "permission.external_directory is not an object")
    normalized = {str(key).replace("\\", "/"): value for key, value in rules.items()}
    expected_rules = [f"{root.as_posix()}/.at/shared/**", f"{root.as_posix()}/.at/sessions/**"]
    missing_rules = [rule for rule in expected_rules if rule not in normalized]
    provider = data.get("provider", {})
    models = provider.get("deepseek", {}).get("models", {}) if isinstance(provider, dict) else {}
    if missing_rules or "deepseek-v4-flash" not in models:
        problems = []
        if missing_rules:
            problems.append("missing external_directory rule(s): " + ", ".join(missing_rules))
        if "deepseek-v4-flash" not in models:
            problems.append("missing deepseek/deepseek-v4-flash model config")
        return CheckResult("opencode_global_config", "FIXABLE", "; ".join(problems))
    return CheckResult("opencode_global_config", "OK", "deepseek config and external_directory rules present")


def provider_commands_fixed(config: dict) -> tuple[dict, list[str]]:
    config = deepcopy(config)
    changes: list[str] = []
    providers = config.setdefault("providers", {})
    codex = providers.setdefault("codex", {})
    codex_command = list(codex.get("command") or [])
    if codex_command and "exec" not in codex_command:
        codex["command"] = [codex_command[0], *CODEX_EXEC_ARGS]
        changes.append("codex command updated to non-interactive exec form")
    opencode = providers.setdefault("opencode", {})
    opencode_command = list(opencode.get("command") or [])
    if opencode_command and (len(opencode_command) < 2 or opencode_command[1] != "run"):
        opencode["command"] = [opencode_command[0], "run"]
        changes.append("opencode command updated to non-interactive run form")
    return config, changes


def _opencode_template(root: Path) -> dict:
    return {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            "deepseek": {
                "models": {
                    "deepseek-v4-flash": {"name": "DeepSeek V4 Flash"},
                }
            }
        },
        "model": "deepseek/deepseek-v4-flash",
        "permission": {
            "external_directory": {
                f"{root.as_posix()}/.at/shared/**": "allow",
                f"{root.as_posix()}/.at/sessions/**": "allow",
            }
        },
    }


def merge_opencode_config(existing: dict | None, root: Path) -> dict:
    template = _opencode_template(root)
    if existing is None:
        return template
    merged = deepcopy(existing)
    provider = merged.setdefault("provider", {})
    deepseek = provider.setdefault("deepseek", {})
    models = deepseek.setdefault("models", {})
    models.setdefault("deepseek-v4-flash", template["provider"]["deepseek"]["models"]["deepseek-v4-flash"])
    merged.setdefault("model", template["model"])
    permission = merged.setdefault("permission", {})
    external = permission.setdefault("external_directory", {})
    normalized = {str(key).replace("\\", "/"): value for key, value in external.items()}
    for key, value in template["permission"]["external_directory"].items():
        if key not in normalized:
            external[key] = value
    return merged


def ensure_workspace(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    from .workspace import ATWorkspace

    workspace = ATWorkspace.init(root) if not (root / "at.config.json").exists() else ATWorkspace.require(root)
    return workspace.root


def ensure_codex_trigger(root: Path) -> Path:
    from .codex_trigger import install_codex_trigger

    at_command = f'python "{root / "at.py"}"'
    return install_codex_trigger(root, at_command=at_command)


def ensure_at_package(root: Path) -> None:
    if _at_package_importable():
        return
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(root)],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"warning: could not install the at_flow package ({exc}); "
            f"the AGENTS.md trigger uses `python \"{root / 'at.py'}\"` so the package install is optional",
            file=sys.stderr,
        )


def _at_package_importable() -> bool:
    import tempfile

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    probe = subprocess.run(
        [sys.executable, "-c", "import at_flow"],
        cwd=tempfile.gettempdir(),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return probe.returncode == 0


def ensure_provider_config(root: Path) -> list[str]:
    config_path = root / "at.config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing {config_path}; run ensure_workspace first")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    fixed, changes = provider_commands_fixed(config)
    if changes:
        config_path.write_text(json.dumps(fixed, indent=2) + "\n", encoding="utf-8")
    return changes


def ensure_opencode_global_config(root: Path) -> str:
    path = opencode_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"cannot create opencode config directory {path.parent}: {exc}; "
            "grant access or create the file manually"
        ) from exc
    existing: dict | None = None
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise RuntimeError(
                f"cannot read {path}: {exc}; grant access or configure opencode manually"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"{path} is not parseable JSON; edit it manually to add the AT Flow rules. "
                f"Original error: {exc}"
            ) from exc
    merged = merge_opencode_config(existing, root)
    try:
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"cannot write {path}: {exc}; grant access or create the file manually"
        ) from exc
    return str(path)


def ensure_python_deps(root: Path) -> None:
    missing = [name for name in REQUIRED_PYTHON_PACKAGES if importlib.util.find_spec(name) is None]
    if missing:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(root / "requirements.txt")],
            check=True,
        )


def ensure_frontend_deps(root: Path) -> None:
    if (root / "web" / "node_modules").exists():
        return
    subprocess.run([resolve_npm(), "ci"], cwd=str(root / "web"), check=True)


def ensure_build(root: Path) -> None:
    subprocess.run([resolve_npm(), "run", "build"], cwd=str(root / "web"), check=True)


def backend_command(root: Path, port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "at_flow.web",
        "--root",
        str(root),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]


def frontend_command(port: int) -> list[str]:
    return [resolve_npm(), "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port)]


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _wait_for_backend(port: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f"backend did not become healthy on port {port} within {timeout}s")


def start_servers(root: Path, backend_port: int = 8000, frontend_port: int = 3000) -> int:
    root = root.resolve()
    ensure_workspace(root)
    log_dir = root / ".at"
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    src = str(root / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    backend_out = open(log_dir / "web-backend.stdout.log", "ab")
    backend_err = open(log_dir / "web-backend.stderr.log", "ab")
    frontend_out = open(log_dir / "web-frontend.stdout.log", "ab")
    frontend_err = open(log_dir / "web-frontend.stderr.log", "ab")
    backend = subprocess.Popen(
        backend_command(root, backend_port),
        cwd=str(root),
        env=env,
        stdout=backend_out,
        stderr=backend_err,
    )
    frontend = subprocess.Popen(
        frontend_command(frontend_port),
        cwd=str(root / "web"),
        env=env,
        stdout=frontend_out,
        stderr=frontend_err,
    )
    processes = [backend, frontend]
    try:
        _wait_for_backend(backend_port)
        frontend_deadline = time.monotonic() + 60
        while time.monotonic() < frontend_deadline:
            if _port_open("127.0.0.1", frontend_port):
                break
            if frontend.poll() is not None:
                raise RuntimeError("frontend dev server exited early; see .at/web-frontend.stderr.log")
            time.sleep(1)
        else:
            raise RuntimeError(f"frontend did not listen on port {frontend_port} within 60s")
        webbrowser.open(f"http://127.0.0.1:{frontend_port}/runtime")
        print(f"backend : http://127.0.0.1:{backend_port}/api/health")
        print(f"frontend: http://127.0.0.1:{frontend_port}/runtime")
        print("press Ctrl+C to stop both servers")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping servers")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        for handle in (backend_out, backend_err, frontend_out, frontend_err):
            handle.close()
    return 0


def run_doctor(root: Path, backend_port: int = 8000, frontend_port: int = 3000) -> int:
    from .inspectors import doctor_checks
    from .workspace import ATWorkspace

    workspace = ATWorkspace.require(root)
    failed = 0
    for name, ok, detail in doctor_checks(workspace):
        marker = "OK " if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"{marker} {name}: {detail}")
    backend_ok = _port_open("127.0.0.1", backend_port)
    frontend_ok = _port_open("127.0.0.1", frontend_port)
    print(f"{'OK ' if backend_ok else 'FAIL'} backend http://127.0.0.1:{backend_port}/api/health")
    print(f"{'OK ' if frontend_ok else 'FAIL'} frontend http://127.0.0.1:{frontend_port}/runtime")
    print_ready_guide(root, backend_port, frontend_port)
    return 1 if (failed or not backend_ok or not frontend_ok) else 0


def print_ready_guide(root: Path, backend_port: int, frontend_port: int) -> None:
    print()
    print("AT Flow ready. Two official entries:")
    print(f"  1. Codex conversation: open Codex in {root} and type `AT`")
    print(f"  2. Web console:        http://127.0.0.1:{frontend_port}/runtime")
    print("     start both servers with: python scripts/setup.py start")

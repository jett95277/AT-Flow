# AT V1.9 Dual Entry And One Click Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让 AT Flow v1.9 双入口（Codex 对话 / Web Console）完整可用，并提供一键配置脚本（check / install / start / doctor / all）。

**Architecture:** 核心逻辑放 `src/at_flow/setup.py`（可 import、可单测），`scripts/setup.py` 为薄 CLI 入口，`setup.cmd` 为根目录 Windows 包装。复用既有 `ATWorkspace`、`install_codex_trigger`、`doctor_checks`；不改 Web 入口形态（保持 uvicorn + vite dev 双进程）。

**Tech Stack:** Python 3.9+（本机 miniconda 3.9.1 实测可用）、FastAPI/uvicorn、npm/vite、codex CLI、opencode CLI、unittest。

## Global Constraints

- 个人辅助开发工具流，不做产品化包装；脚本输出可解释、幂等、可验证。
- 双入口共享同一 AT runtime；脚本不改变既有架构与目录布局。
- 不静默降级：环境缺项、依赖失败、provider 不可用必须显式报告。
- 幂等：`install` 可重复执行，不覆盖用户已有 at.config.json、AGENTS.md、opencode 全局配置、`.at` 数据。
- opencode 全局配置只补缺失项（用户已确认允许）；解析失败时提示手动处理，不破坏性重写。
- Windows 下命令解析优先 `npm.cmd` / `codex.cmd` / `opencode.cmd`，避开 PowerShell 执行策略对 `.ps1` 的限制。
- **按用户当前指令：v1.9 收尾完成前不 commit / 不 push；所有改动最后统一提交。** 每个任务以"记录变更"收尾，不执行 git commit。
- 规格来源：`docs/superpowers/specs/2026-08-03-at-v1-9-dual-entry-and-one-click-setup-design.md`。

---

### Task 1: setup 核心模块 —— 环境体检（check）

**Files:**
- Create: `src/at_flow/setup.py`
- Test: `tests/test_setup.py`

**Interfaces:**
- Consumes: `at_flow.workspace.ATWorkspace`、`at_flow.inspectors.doctor_checks`、`at_flow.codex_trigger.BEGIN_MARKER`。
- Produces:
  - `@dataclass CheckResult` 字段 `name: str`、`status: str`（`OK|MISSING|FIXABLE|ERROR`）、`detail: str`。
  - `environment_report(root: Path) -> list[CheckResult]`：只读体检，覆盖 python 依赖、node/npm、codex/opencode 命令、`.at` 初始化、AGENTS.md 触发块、at.config.json provider 命令、opencode 全局配置。
  - `resolve_npm() -> str`：Windows 返回 `npm.cmd`，否则 `npm`。
  - `opencode_config_path(home: Path | None = None) -> Path`：默认 `Path.home()/".config"/"opencode"/"opencode.jsonc"`。

- [x] **Step 1: 写失败测试**

```python
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))

from at_flow.setup import CheckResult, environment_report, opencode_config_path, resolve_npm


class SetupCheckTests(unittest.TestCase):
    def test_opencode_config_path_uses_home_config_dir(self):
        self.assertEqual(
            opencode_config_path(Path("C:/Users/test")),
            Path("C:/Users/test/.config/opencode/opencode.jsonc"),
        )

    def test_environment_report_flags_missing_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            report = environment_report(Path(directory))
            workspace_check = next(item for item in report if item.name == "at_workspace")
            self.assertEqual(workspace_check.status, "MISSING")

    def test_environment_report_reports_ok_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "at.config.json").write_text("{}", encoding="utf-8")
            report = environment_report(root)
            workspace_check = next(item for item in report if item.name == "at_workspace")
            self.assertEqual(workspace_check.status, "OK")


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: 运行确认失败**

Run: `python -m unittest tests.test_setup -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'at_flow.setup'`

- [x] **Step 3: 最小实现**

```python
from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import shutil
import sys


REQUIRED_PYTHON_PACKAGES = ("fastapi", "uvicorn", "httpx")


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
    results: list[CheckResult] = []
    results.append(_check_python_packages())
    results.append(_check_command("node", shutil.which("node")))
    results.append(_check_command("npm", shutil.which(resolve_npm())))
    results.append(_check_command("codex", shutil.which("codex")))
    results.append(_check_command("opencode", shutil.which("opencode")))
    results.append(_check_at_workspace(root))
    results.append(_check_agents_trigger(root))
    results.append(_check_provider_commands(root))
    results.append(_check_opencode_global_config(root))
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
    return CheckResult("at_workspace", "MISSING", "run `python scripts/setup.py install` or `python at.py init`")


def _check_agents_trigger(root: Path) -> CheckResult:
    agents_path = root / "AGENTS.md"
    if agents_path.exists() and "AT_FLOW_TRIGGER_BEGIN" in agents_path.read_text(encoding="utf-8"):
        return CheckResult("codex_trigger", "OK", "AGENTS.md contains AT trigger block")
    return CheckResult("codex_trigger", "MISSING", "AGENTS.md trigger block not installed")


def _check_provider_commands(root: Path) -> CheckResult:
    config_path = root / "at.config.json"
    if not config_path.exists():
        return CheckResult("provider_commands", "MISSING", "at.config.json missing")
    import json
    config = json.loads(config_path.read_text(encoding="utf-8"))
    providers = config.get("providers", {})
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
    if not path.exists():
        return CheckResult("opencode_global_config", "MISSING", f"{path} does not exist")
    try:
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return CheckResult("opencode_global_config", "ERROR", f"{path} not parseable: {exc}")
    rules = data.get("permission", {}).get("external_directory", {})
    expected = f"{root.as_posix()}/.at/shared/**"
    if not any(key.replace("\\", "/") == expected for key in rules):
        return CheckResult("opencode_global_config", "FIXABLE", "missing .at/shared external_directory rule")
    return CheckResult("opencode_global_config", "OK", "deepseek config and external_directory rules present")
```

- [x] **Step 4: 运行确认通过**

Run: `python -m unittest tests.test_setup -v`
Expected: PASS（3 个用例）

- [x] **Step 5: 运行既有测试确认无回归**

Run: `python -m unittest discover -s tests`
Expected: OK（129 + 新增）

- [x] **Step 6: 记录变更**

`tests/test_setup.py`、`src/at_flow/setup.py` 待 v1.9 收尾统一提交（不 commit）。

---

### Task 2: install 逻辑（依赖/工作区/触发块/命令修复/opencode 配置）

**Files:**
- Modify: `src/at_flow/setup.py`
- Modify: `tests/test_setup.py`

**Interfaces:**
- Consumes: `at_flow.workspace.ATWorkspace`、`at_flow.codex_trigger.install_codex_trigger`。
- Produces:
  - `provider_commands_fixed(config: dict) -> tuple[dict, list[str]]`：返回修复后的 config 与变更说明列表。
  - `merge_opencode_config(existing: dict | None, root: Path) -> dict`：返回合并后的 opencode 配置（模板或深合并）。
  - `ensure_workspace(root: Path) -> Path`、`ensure_codex_trigger(root: Path) -> Path`、`ensure_provider_config(root: Path) -> list[str]`、`ensure_opencode_global_config(root: Path) -> str`、`ensure_python_deps(root: Path) -> None`、`ensure_frontend_deps(root: Path) -> None`、`ensure_build(root: Path) -> None`。

- [x] **Step 1: 写失败测试（纯函数）**

```python
from at_flow.setup import merge_opencode_config, provider_commands_fixed


class SetupInstallLogicTests(unittest.TestCase):
    def test_provider_commands_fixed_adds_codex_exec_and_opencode_run(self):
        config = {
            "providers": {
                "codex": {"command": ["codex"]},
                "opencode": {"command": ["opencode"]},
            }
        }
        fixed, changes = provider_commands_fixed(config)
        self.assertIn("exec", fixed["providers"]["codex"]["command"])
        self.assertEqual(fixed["providers"]["opencode"]["command"], ["opencode", "run"])
        self.assertEqual(len(changes), 2)

    def test_provider_commands_fixed_keeps_custom_executable(self):
        config = {"providers": {"codex": {"command": ["my-codex"]}}}
        fixed, _ = provider_commands_fixed(config)
        self.assertEqual(fixed["providers"]["codex"]["command"][0], "my-codex")
        self.assertIn("exec", fixed["providers"]["codex"]["command"])

    def test_provider_commands_fixed_keeps_existing_non_interactive(self):
        config = {
            "providers": {
                "codex": {"command": ["codex", "exec", "--ephemeral", "-"]},
                "opencode": {"command": ["opencode", "run"]},
            }
        }
        fixed, changes = provider_commands_fixed(config)
        self.assertEqual(changes, [])
        self.assertEqual(fixed["providers"]["opencode"]["command"], ["opencode", "run"])

    def test_merge_opencode_config_creates_template(self):
        merged = merge_opencode_config(None, Path("E:/AT FLOW"))
        self.assertEqual(merged["model"], "deepseek/deepseek-v4-flash")
        self.assertIn("E:/AT FLOW/.at/shared/**", merged["permission"]["external_directory"])

    def test_merge_opencode_config_preserves_existing_keys(self):
        existing = {"model": "anthropic/claude-sonnet", "permission": {"bash": "allow"}}
        merged = merge_opencode_config(existing, Path("E:/AT FLOW"))
        self.assertEqual(merged["model"], "anthropic/claude-sonnet")
        self.assertEqual(merged["permission"]["bash"], "allow")
        self.assertIn("E:/AT FLOW/.at/shared/**", merged["permission"]["external_directory"])

    def test_merge_opencode_config_adds_missing_deepseek_model(self):
        existing = {"permission": {"external_directory": {"C:/other/**": "allow"}}}
        merged = merge_opencode_config(existing, Path("E:/AT FLOW"))
        self.assertEqual(merged["provider"]["deepseek"]["models"]["deepseek-v4-flash"]["name"], "DeepSeek V4 Flash")
        self.assertIn("C:/other/**", merged["permission"]["external_directory"])
```

- [x] **Step 2: 运行确认失败**

Run: `python -m unittest tests.test_setup -v`
Expected: FAIL —— `NameError/AttributeError: provider_commands_fixed / merge_opencode_config 不存在`

- [x] **Step 3: 最小实现（追加到 setup.py）**

```python
from copy import deepcopy
import json
import os
import subprocess


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
    for key, value in template["permission"]["external_directory"].items():
        normalized = {str(k).replace("\\", "/"): v for k, v in external.items()}
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
    return install_codex_trigger(root)


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
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict | None = None
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(
                f"{path} is not parseable JSON; edit it manually to add the AT Flow rules. Original error: {exc}"
            ) from exc
    merged = merge_opencode_config(existing, root)
    path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return str(path)


def ensure_python_deps(root: Path) -> None:
    missing = [name for name in REQUIRED_PYTHON_PACKAGES if importlib.util.find_spec(name) is None]
    if not missing:
        return
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
```

- [x] **Step 4: 运行确认通过**

Run: `python -m unittest tests.test_setup -v`
Expected: PASS（6 个新用例）

- [x] **Step 5: 记录变更**

同上（统一提交）。

---

### Task 3: start 双进程启动与停止

**Files:**
- Modify: `src/at_flow/setup.py`
- Modify: `tests/test_setup.py`

**Interfaces:**
- Consumes: `environment_report`、`ensure_workspace`、`ensure_provider_config`、`ensure_codex_trigger`。
- Produces:
  - `backend_command(root: Path, port: int) -> list[str]`
  - `frontend_command(port: int) -> list[str]`
  - `start_servers(root: Path, backend_port: int = 8000, frontend_port: int = 3000) -> int`
  - `_port_open(host: str, port: int) -> bool`

- [x] **Step 1: 写失败测试（命令构造 + 端口探测）**

```python
from at_flow.setup import _port_open, backend_command, frontend_command, resolve_npm


class SetupStartTests(unittest.TestCase):
    def test_backend_command_contains_web_module_and_root(self):
        cmd = backend_command(Path("E:/AT FLOW"), 8123)
        self.assertIn("-m", cmd)
        self.assertIn("at_flow.web", cmd)
        self.assertIn("--port", cmd)
        self.assertEqual(cmd[cmd.index("--port") + 1], "8123")
        self.assertEqual(cmd[cmd.index("--root") + 1], "E:/AT FLOW")

    def test_frontend_command_runs_dev_server(self):
        cmd = frontend_command(3123)
        self.assertEqual(cmd[0], resolve_npm())
        self.assertIn("dev", cmd)

    def test_port_open_false_for_unused_port(self):
        self.assertFalse(_port_open("127.0.0.1", 1))
```

- [x] **Step 2: 运行确认失败**

Run: `python -m unittest tests.test_setup -v`
Expected: FAIL —— 函数不存在

- [x] **Step 3: 最小实现**

```python
import socket
import time
import urllib.request
import webbrowser


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
```

- [x] **Step 4: 运行确认通过**

Run: `python -m unittest tests.test_setup -v`
Expected: PASS（3 个新用例）

- [x] **Step 5: 记录变更**

同上。

---

### Task 4: doctor 与就绪报告

**Files:**
- Modify: `src/at_flow/setup.py`
- Modify: `tests/test_setup.py`

**Interfaces:**
- Consumes: `at_flow.inspectors.doctor_checks`、`_port_open`。
- Produces: `run_doctor(root: Path, backend_port: int = 8000, frontend_port: int = 3000) -> int`、`print_ready_guide(root: Path, backend_port: int, frontend_port: int) -> None`。

- [x] **Step 1: 写失败测试**

```python
from at_flow.setup import print_ready_guide


class SetupDoctorTests(unittest.TestCase):
    def test_print_ready_guide_lists_both_entries(self):
        lines: list[str] = []
        original = print
        def fake_print(*args, **kwargs):
            lines.append(" ".join(str(item) for item in args))
        globals()["print"] = fake_print
        try:
            print_ready_guide(Path("E:/AT FLOW"), 8000, 3000)
        finally:
            globals()["print"] = original
        joined = "\n".join(lines)
        self.assertIn("Codex", joined)
        self.assertIn("http://127.0.0.1:3000/runtime", joined)
```

- [x] **Step 2: 运行确认失败**

Run: `python -m unittest tests.test_setup -v`
Expected: FAIL —— 函数不存在

- [x] **Step 3: 最小实现**

```python
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
```

- [x] **Step 4: 运行确认通过**

Run: `python -m unittest tests.test_setup -v`
Expected: PASS（1 个新用例）

- [x] **Step 5: 记录变更**

同上。

---

### Task 5: CLI 入口与 setup.cmd 包装

**Files:**
- Create: `scripts/setup.py`
- Create: `setup.cmd`
- Modify: `tests/test_setup.py`

**Interfaces:**
- Consumes: `at_flow.setup` 全部公开函数。
- Produces: `scripts/setup.py main(argv=None) -> int`；`setup.cmd` 透传参数。

- [x] **Step 1: 写失败测试（CLI 分发逻辑，用临时目录 + mock）**

```python
import io
from contextlib import redirect_stdout
from at_flow import setup as at_setup


class SetupCliTests(unittest.TestCase):
    def test_cli_check_prints_report(self):
        with tempfile.TemporaryDirectory() as directory:
            import scripts_setup_shim  # see Step 3 note
```

为保持测试简单：CLI 分发逻辑在 `scripts/setup.py` 中保持薄，核心行为已由 `environment_report` / `run_doctor` 覆盖；本任务测试改为验证 `scripts/setup.py` 可被 import 且暴露 `main`：

```python
class SetupScriptTests(unittest.TestCase):
    def test_scripts_setup_exposes_main(self):
        import runpy
        namespace = runpy.run_path(str(ROOT / "scripts" / "setup.py"))
        self.assertTrue(callable(namespace["main"]))

    def test_scripts_setup_help_exits_zero(self):
        import runpy
        namespace = runpy.run_path(str(ROOT / "scripts" / "setup.py"))
        result = namespace["main"](["--help"])
        self.assertEqual(result, 0)
```

- [x] **Step 2: 运行确认失败**

Run: `python -m unittest tests.test_setup -v`
Expected: FAIL —— `scripts/setup.py` 不存在（FileNotFoundError）

- [x] **Step 3: 实现**

`scripts/setup.py`：

```python
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
        changes = at_setup.ensure_provider_config(root)
        for change in changes:
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
            print("blocking errors found; run install after fixing prerequisites", file=sys.stderr)
            return 1
        at_setup.ensure_python_deps(root)
        at_setup.ensure_frontend_deps(root)
        at_setup.ensure_build(root)
        at_setup.ensure_workspace(root)
        at_setup.ensure_codex_trigger(root)
        for change in at_setup.ensure_provider_config(root):
            print(f"fixed: {change}")
        at_setup.ensure_opencode_global_config(root)
        return at_setup.run_doctor(root, args.backend_port, args.frontend_port)
    parser.error(f"unknown command: {args.command}")
    return 2


def _print_report(report: list, fail_on_error: bool = False) -> int:
    failed = 0
    for item in report:
        marker = {"OK": "OK ", "FIXABLE": "FIX", "MISSING": "MISS", "ERROR": "ERR"}[item.status]
        if item.status in {"MISSING", "ERROR", "FIXABLE"}:
            failed += 1
        print(f"[{marker}] {item.name}: {item.detail}")
    if fail_on_error and failed:
        print(f"{failed} item(s) need attention", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`setup.cmd`：

```cmd
@echo off
setlocal
python "%~dp0scripts\setup.py" %*
exit /b %ERRORLEVEL%
```

- [x] **Step 4: 运行确认通过**

Run: `python -m unittest tests.test_setup -v`
Expected: PASS（2 个新用例）
Run: `python scripts/setup.py check`
Expected: 输出完整体检报告

- [x] **Step 5: 记录变更**

同上。

---

### Task 6: 文档与配置一致性

**Files:**
- Modify: `README.md`（一键脚本用法 + 双入口启动说明）
- Modify: `docs/developing-at.md`（补充脚本使用）
- Modify: `agent.md`（记录 V1.9 收尾状态）
- Modify: `pyproject.toml`（`requires-python = ">=3.10"` → `">=3.9"`，与实测依赖一致）
- Modify: `.gitignore`（追加 `.claude/`，避免本地工具配置入库）

- [x] **Step 1: 更新 README 脚本章节**

在 README 的"两种使用方式"后追加：

```markdown
## 一键配置

```powershell
python scripts/setup.py check
python scripts/setup.py install
python scripts/setup.py start
python scripts/setup.py doctor
```

或直接：

```powershell
setup.cmd all
```
```

- [x] **Step 2: 更新 agent.md 与 developing-at.md**

`agent.md` 追加 V1.9 收尾状态（一键脚本 + 双入口验证结果）；`developing-at.md` 补充 setup 脚本使用说明。

- [x] **Step 3: 更新 pyproject 与 .gitignore**

`pyproject.toml`：`requires-python = ">=3.9"`。
`.gitignore` 追加一行 `.claude/`。

- [x] **Step 4: 验证**

Run: `python -m unittest discover -s tests`
Run: `npm.cmd test -- --run`（workdir `web`）
Expected: 全通过

- [x] **Step 5: 记录变更**

同上。

---

### Task 7: 双入口真实验证

**Files:**
- No source changes（仅验证；发现缺陷才改）。

- [x] **Step 1: CLI 入口验证（mock）**

Run: `python at.py start "setup-e2e-mock" --provider mock --run`
Expected: 会话创建并跑完 main 步骤

- [x] **Step 2: Codex 对话触发块验证**

Run: `python at.py enable --target "E:\AT FLOW"` 后检查 `AGENTS.md` 含触发块；再 `python at.py panel --format chat`
Expected: 触发块存在，面板输出正常

- [x] **Step 3: codex / opencode provider 实测**

Run: `python at.py start "setup-e2e-codex" --provider codex --run`（`agent_providers` 路由：code 步骤用 codex）
Run: opencode provider 单步（复用之前 E2E 会话方式）
Expected: 步骤 done；无法联网时明确记录"未验证"

- [x] **Step 4: Web 入口验证**

Run: `python scripts/setup.py start`，然后：
`Invoke-RestMethod http://127.0.0.1:8000/api/health`、`http://127.0.0.1:8000/api/providers`、创建会话 + run-one-step
Expected: 健康、provider 列表、会话推进正常

- [x] **Step 5: 语言契约验证**

创建中文任务会话，检查 `language.json` 的 `task_runtime` 为英文、前端展示为中文。
Expected: 中英链路正确

- [x] **Step 6: 记录结果**

把验证结果写入 agent.md 的 V1.9 收尾状态。

---

### Task 8: 全量验证与收尾

- [x] **Step 1: 后端全量测试**

Run: `python -m unittest discover -s tests`
Expected: OK（129 + setup 新增）
Actual: OK（146 tests）

- [x] **Step 2: 前端测试与构建**

Run: `npm.cmd test -- --run`；`npm.cmd run build`（workdir `web`）
Expected: 38 通过；build 成功
Actual: 38 passed; build passed

- [x] **Step 3: git 状态核对**

Run: `git status --short`、`git diff --check`
Expected: 无空白错误；`.claude/` 已忽略；全部改动符合预期

- [x] **Step 4: 更新计划状态**

本计划与 spec 的 checkbox 全部勾选，验证数字同步。

- [x] **Step 5: 汇总报告**

向用户报告：改动文件、验证结果、遗留风险（如联网项未验证）、下一步（用户批准后统一 commit + push）。

## Execution Status

```text
Status: complete
Backend tests: 146 passed (129 + 16 setup + 1 prompt contract)
Frontend tests: 38 passed; production build passed
Live verification:
  CLI mock pipeline: main->analysis->code->test all OK
  Codex trigger: AGENTS.md installed with `python "<root>\at.py"` command
  Live codex code/test steps passed (deepseek-v4-flash)
  Language contract: zh->en->zh, artifact.zh.md generated
  Web entry: health/providers/session-create/run-one-step OK, vite dev reachable
Defects found and fixed during Task 7:
  1. build_prompt lacked artifact language rules; model prefixed artifact with
     Chinese narrative and the language contract rejected it -> added
     "Artifact output rules" (entirely English, no preamble) + test
  2. AGENTS.md trigger used `python -m at_flow`, which fails on this machine
     (package not installed; setuptools 61.2 lacks PEP 660, pip cannot copy
     .git checkpoints) -> cmd_enable/setup now emit `python "<root>\at.py"`
  3. pip/network on this machine: proxy SSL issue documented in README; package
     install treated as optional with explicit warning (ensure_at_package)
Git: changes not committed/pushed per user instruction; staged later after v1.9 approval
```

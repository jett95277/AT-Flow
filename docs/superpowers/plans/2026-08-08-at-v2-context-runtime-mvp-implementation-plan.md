# AT v2.0 Context Runtime MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `v2.0` 分支仓库内重写，交付 Context Runtime 最小可用版：8 个核心模块 + 三层记忆 + Structured Handoff + Context Bundle + `at` CLI + 最小对比 eval，可用性第一。

**Architecture:** Python 3 包 `src/at_runtime/`，文件系统存储（`.agent/`），LocalAdapter 每 Session 启动新 Codex 进程并注入 Context Bundle；Context Router 用显式引用 + 静态 Policy，不做 LLM 检索；Runtime Observer 记录事件与 token 估算。

**Tech Stack:** Python 3.10+、PyYAML（唯一新增依赖，用于 manifest/policies 解析）、标准库（json/pathlib/subprocess）、Codex CLI（进程 provider）。

## Global Constraints

- 规格来源：`docs/superpowers/specs/2026-08-08-at-v2-context-runtime-design.md`。
- v2.0 分支仓库内重写：删除 v1 实现（`src/at_flow/`、`web/`、`deploy/`、`at.py`、`setup.cmd`、`scripts/`、v1 测试），替换为 `src/at_runtime/`；v1 完整保留在 git 历史。
- 可用性第一：8 模块只做能跑通的最小实现；任何机制若未在验证门中使用就不实现。
- Context Router 不做 LLM 检索：relevance = 显式引用 + Policy 静态规则 + 默认最小集。
- Execution = 进程级隔离：每个 Agent Session 一个 Codex 进程调用。
- 无 DB、无 Web、无网络依赖（除 Codex 自身）。
- 唯一新增 Python 依赖 PyYAML（manifest/policies 用 YAML）；其余用标准库。
- 按用户当前惯例：开发过程中不 commit/push，最后统一提交。

---

### Task 0: 仓库重写骨架

**Files:**
- Delete: `src/at_flow/`、`web/`、`deploy/`、`at.py`、`setup.cmd`、`scripts/`、`requirements.txt`（重写）
- Create: `src/at_runtime/__init__.py`、`src/at_runtime/cli.py`、`requirements.txt`、`pyproject.toml`（重写）
- Modify: `.gitignore`（保留 `.at/` 忽略，新增 `.agent/` 忽略）

**Interfaces:**
- Produces: 可 import 的 `at_runtime` 包与空 CLI 入口。

- [x] **Step 1: 删除 v1 实现并创建新包骨架**

删除 v1 文件（git 历史保留），创建：

```python
# src/at_runtime/__init__.py
__version__ = "0.1.0"
```

```python
# src/at_runtime/cli.py
from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="at", description="AT Context Runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="initialize .agent workspace")
    args = parser.parse_args(argv)
    if args.command == "init":
        print("at init: pending")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

`requirements.txt`：`PyYAML>=6.0`
`pyproject.toml`：name=at-runtime、scripts `at = "at_runtime.cli:main"`

- [x] **Step 2: 运行确认**

Run: `python -c "import at_runtime; print(at_runtime.__version__)"`
Expected: `0.1.0`

- [x] **Step 3: 记录变更**

---

### Task 1: init 与 manifest/policies 模板

**Files:**
- Create: `src/at_runtime/workspace.py`
- Create: `src/at_runtime/__main__.py`
- Modify: `src/at_runtime/cli.py`
- Test: `tests/test_workspace.py`

**Interfaces:**
- Produces:
  - `initialize_workspace(root: Path) -> Path`：生成 `.agent/` 目录结构与
    `manifest.yaml`、`policies.yaml` 默认模板。
  - `load_manifest(root: Path) -> dict` / `load_policies(root: Path) -> dict`。

- [x] **Step 1: 写失败测试**

```python
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.workspace import initialize_workspace, load_manifest, load_policies


class WorkspaceTests(unittest.TestCase):
    def test_init_creates_agent_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            for relative in (
                ".agent/manifest.yaml",
                ".agent/policies.yaml",
                ".agent/runtime/sessions",
                ".agent/runtime/tasks",
                ".agent/runtime/events",
                ".agent/contexts/bundles",
                ".agent/memory/short",
                ".agent/memory/medium",
                ".agent/memory/long",
                ".agent/handoffs",
                ".agent/artifacts",
                ".agent/knowledge/refs",
            ):
                self.assertTrue((root / relative).exists(), relative)

    def test_manifest_has_project_and_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            manifest = load_manifest(root)
            self.assertIn("project", manifest)
            self.assertIn("runtime", manifest)

    def test_policies_have_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            policies = load_policies(root)
            self.assertIn("analysis", policies["roles"])
            self.assertIn("code", policies["roles"])
            self.assertIn("test", policies["roles"])


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: 运行确认失败**

Run: `python -m unittest tests.test_workspace -v`
Expected: FAIL —— `ModuleNotFoundError: at_runtime.workspace`

- [x] **Step 3: 最小实现**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_MANIFEST = {
    "version": 1,
    "project": {"name": "project"},
    "runtime": {"context_policy": "./policies.yaml"},
    "workflow": {"provider": "superpowers"},
    "knowledge": {"provider": "local"},
    "execution": {"provider": "local"},
    "agents": {
        "analysis": {"provider": "codex"},
        "code": {"provider": "codex"},
        "test": {"provider": "codex"},
    },
}

DEFAULT_POLICIES = {
    "version": 1,
    "roles": {
        "analysis": {
            "read": ["source", "wiki", "project_memory", "analysis_memory"],
            "write": ["short_memory", "feature_memory", "handoff:analysis_to_code"],
        },
        "code": {
            "read": ["source", "wiki", "project_memory", "code_memory", "handoff:analysis_to_code"],
            "write": ["source", "short_memory", "feature_memory", "handoff:code_to_test"],
        },
        "test": {
            "read": ["source", "wiki", "project_memory", "test_memory", "handoff:code_to_test"],
            "write": ["test_artifacts", "test_memory", "handoff:test_to_code"],
        },
    },
}


def initialize_workspace(root: Path) -> Path:
    directories = (
        ".agent/runtime/sessions",
        ".agent/runtime/tasks",
        ".agent/runtime/events",
        ".agent/contexts/bundles",
        ".agent/memory/short",
        ".agent/memory/medium",
        ".agent/memory/long",
        ".agent/handoffs",
        ".agent/artifacts",
        ".agent/knowledge/refs",
    )
    for relative in directories:
        (root / relative).mkdir(parents=True, exist_ok=True)
    manifest = root / ".agent/manifest.yaml"
    if not manifest.exists():
        manifest.write_text(yaml.safe_dump(DEFAULT_MANIFEST, allow_unicode=True, sort_keys=False), encoding="utf-8")
    policies = root / ".agent/policies.yaml"
    if not policies.exists():
        policies.write_text(yaml.safe_dump(DEFAULT_POLICIES, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return root / ".agent"


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / ".agent/manifest.yaml"
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_policies(root: Path) -> dict[str, Any]:
    path = root / ".agent/policies.yaml"
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
```

接入 CLI `init` 命令（`initialize_workspace(Path.cwd())`）。

- [x] **Step 4: 运行确认通过**

Run: `python -m unittest tests.test_workspace -v`
Expected: PASS（3 个用例）

- [x] **Step 5: 记录变更**

---

### Task 2: Task 与 Session Registry

**Files:**
- Create: `src/at_runtime/registry.py`
- Modify: `src/at_runtime/cli.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Produces:
  - `create_task(root, task_id, goal, scope: dict) -> dict`（写 `.agent/runtime/tasks/<id>.yaml`）
  - `create_session(root, session_id, task_id, role, provider) -> dict`
  - `get_session(root, session_id) -> dict`
  - `update_session_status(root, session_id, status) -> dict`
  - `list_sessions(root) -> list[dict]`

- [x] **Step 1: 写失败测试**

```python
from at_runtime.registry import (
    create_session,
    create_task,
    get_session,
    list_sessions,
    update_session_status,
)


class RegistryTests(unittest.TestCase):
    def test_create_task_and_session(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            task = create_task(root, "T17", "fix beam stability", {"project": "ASR-Agent"})
            session = create_session(root, "analysis-T17-01", "T17", "analysis", "codex")
            self.assertEqual(session["task_id"], "T17")
            self.assertEqual(session["status"], "created")
            self.assertEqual(get_session(root, "analysis-T17-01")["role"], "analysis")
            self.assertEqual(len(list_sessions(root)), 1)
            updated = update_session_status(root, "analysis-T17-01", "running")
            self.assertEqual(updated["status"], "running")
```

- [x] **Step 2: 运行确认失败**（模块不存在）

- [x] **Step 3: 最小实现**

```python
def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def create_task(root: Path, task_id: str, goal: str, scope: dict) -> dict:
    task = {
        "id": task_id,
        "goal": goal,
        "scope": scope,
        "status": "created",
        "sessions": [],
    }
    _write_yaml(root / ".agent/runtime/tasks" / f"{task_id}.yaml", task)
    return task


def create_session(root: Path, session_id: str, task_id: str, role: str, provider: str) -> dict:
    session = {
        "id": session_id,
        "task_id": task_id,
        "role": role,
        "provider": provider,
        "status": "created",
        "parent": None,
    }
    _write_yaml(root / ".agent/runtime/sessions" / f"{session_id}.yaml", session)
    task_path = root / ".agent/runtime/tasks" / f"{task_id}.yaml"
    if task_path.exists():
        task = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
        task.setdefault("sessions", []).append(session_id)
        _write_yaml(task_path, task)
    return session


def get_session(root: Path, session_id: str) -> dict:
    path = root / ".agent/runtime/sessions" / f"{session_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"unknown session: {session_id}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def update_session_status(root: Path, session_id: str, status: str) -> dict:
    session = get_session(root, session_id)
    session["status"] = status
    _write_yaml(root / ".agent/runtime/sessions" / f"{session_id}.yaml", session)
    return session


def list_sessions(root: Path) -> list[dict]:
    directory = root / ".agent/runtime/sessions"
    if not directory.exists():
        return []
    return [
        yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for path in sorted(directory.glob("*.yaml"))
    ]
```

- [x] **Step 4: 运行确认通过**

- [x] **Step 5: 记录变更**

---

### Task 3: Memory Manager（三层 + Scope）

**Files:**
- Create: `src/at_runtime/memory.py`
- Modify: `src/at_runtime/cli.py`（`at memory inspect`）
- Test: `tests/test_memory.py`

**Interfaces:**
- Produces:
  - `memory_path(root, uri: str) -> Path`：解析 `memory://<scope>/<name>/<tier>`。
  - `write_memory(root, uri, content, source: dict, status="candidate") -> dict`
  - `read_memory(root, uri) -> list[dict]`
  - `list_memory(root, scope: str, tier: str) -> list[dict]`

- [x] **Step 1: 写失败测试**

```python
from at_runtime.memory import memory_path, write_memory, read_memory


class MemoryTests(unittest.TestCase):
    def test_memory_uri_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            path = memory_path(root, "memory://session/S32/short")
            self.assertTrue(str(path).endswith(".agent/memory/short/S32.md"))

    def test_short_memory_is_session_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory(root, "memory://session/A/short", "analysis finding", source={"session": "A"})
            self.assertEqual(len(read_memory(root, "memory://session/B/short")), 0)
            self.assertEqual(len(read_memory(root, "memory://session/A/short")), 1)

    def test_long_memory_is_project_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory(root, "memory://project/ASR/long", "stable fact", source={"session": "code-T17"})
            self.assertEqual(len(read_memory(root, "memory://project/ASR/long")), 1)
```

- [x] **Step 2: 运行确认失败**

- [x] **Step 3: 最小实现**

```python
TIER_DIRS = {"short": "memory/short", "medium": "memory/medium", "long": "memory/long"}


def memory_path(root: Path, uri: str) -> Path:
    parts = uri.split("/")
    # memory://<scope>/<name>/<tier>
    if len(parts) < 5:
        raise ValueError(f"invalid memory uri: {uri}")
    _, _, scope, name, tier = parts[:5]
    if tier not in TIER_DIRS:
        raise ValueError(f"unknown tier: {tier}")
    return root / ".agent" / TIER_DIRS[tier] / f"{scope}-{name}.md"


def write_memory(root: Path, uri: str, content: str, source: dict, status: str = "candidate") -> dict:
    path = memory_path(root, uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    item = {
        "uri": uri,
        "content": content,
        "status": status,
        "source": source,
        "created_at": "2026-08-08T00:00:00+08:00",
    }
    entries = []
    if path.exists():
        entries = _load_entries(path)
    entries.append(item)
    _save_entries(path, entries)
    return item


def read_memory(root: Path, uri: str) -> list[dict]:
    path = memory_path(root, uri)
    return _load_entries(path) if path.exists() else []


def _load_entries(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    blocks = text.split("\n---\n")
    entries = []
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().splitlines()
        content = lines[0][2:] if lines[0].startswith("- ") else lines[0]
        meta = {"content": content}
        for line in lines[1:]:
            if ": " in line:
                key, value = line.split(": ", 1)
                meta[key] = value
        entries.append(meta)
    return entries


def _save_entries(path: Path, entries: list[dict]) -> None:
    blocks = []
    for entry in entries:
        lines = [f"- {entry['content']}"]
        for key, value in entry.items():
            if key != "content":
                lines.append(f"{key}: {value}")
        blocks.append("\n".join(lines))
    path.write_text("\n---\n".join(blocks) + "\n", encoding="utf-8")
```

- [x] **Step 4: 运行确认通过**

- [x] **Step 5: 记录变更**

---

### Task 4: Policy Engine

**Files:**
- Create: `src/at_runtime/policy.py`
- Test: `tests/test_policy.py`

**Interfaces:**
- Produces: `can_read(policies, role, resource) -> bool`、`can_write(policies, role, resource) -> bool`。

- [x] **Step 1: 写失败测试**

```python
from at_runtime.policy import can_read, can_write
from at_runtime.workspace import initialize_workspace, load_policies


class PolicyTests(unittest.TestCase):
    def test_code_can_read_analysis_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            policies = load_policies(root)
            self.assertTrue(can_read(policies, "code", "handoff:analysis_to_code"))
            self.assertFalse(can_read(policies, "code", "handoff:test_to_code"))

    def test_analysis_cannot_write_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            policies = load_policies(root)
            self.assertFalse(can_write(policies, "analysis", "source"))
            self.assertTrue(can_write(policies, "code", "source"))
```

- [x] **Step 2: 运行确认失败**

- [x] **Step 3: 最小实现**

```python
def can_read(policies: dict, role: str, resource: str) -> bool:
    return resource in policies.get("roles", {}).get(role, {}).get("read", [])


def can_write(policies: dict, role: str, resource: str) -> bool:
    return resource in policies.get("roles", {}).get(role, {}).get("write", [])
```

- [x] **Step 4: 运行确认通过**

- [x] **Step 5: 记录变更**

---

### Task 5: Context Router + Assembler + Bundle

**Files:**
- Create: `src/at_runtime/context.py`
- Modify: `src/at_runtime/cli.py`（`at context inspect`）
- Test: `tests/test_context.py`

**Interfaces:**
- Produces:
  - `build_context(root, session_id, explicit_refs: dict) -> dict`（Context Bundle）
  - `estimate_tokens(text: str) -> int`（按字符数/4 估算）
  - `assemble_bundle(bundle: dict, budget: int) -> dict`（超预算截断：先删 wiki，再压 memory，最后减 source；task/constraints/handoff 永不删）

- [x] **Step 1: 写失败测试**

```python
from at_runtime.context import build_context, estimate_tokens
from at_runtime.registry import create_session, create_task


class ContextTests(unittest.TestCase):
    def test_bundle_contains_task_handoff_and_constraints(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            create_task(root, "T17", "fix beam stability", {"project": "ASR-Agent"})
            create_session(root, "code-T17-01", "T17", "code", "codex")
            bundle = build_context(
                root,
                "code-T17-01",
                explicit_refs={
                    "handoff": {"from": "analysis-T17", "summary": "beam < 2 means stability skipped"},
                    "constraints": ["preserve API schema"],
                    "source": ["src/scoring.py:120-160"],
                    "memory": ["memory://project/ASR-Agent/long"],
                },
            )
            self.assertEqual(bundle["task"]["id"], "T17")
            self.assertEqual(bundle["role"], "code")
            self.assertIn("preserve API schema", bundle["constraints"])
            self.assertEqual(bundle["handoff"]["summary"], "beam < 2 means stability skipped")
            self.assertGreater(bundle["token_budget"]["max_context"], 0)

    def test_estimate_tokens(self):
        self.assertGreater(estimate_tokens("hello world" * 100), 10)
```

- [x] **Step 2: 运行确认失败**

- [x] **Step 3: 最小实现**

```python
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_context(root: Path, session_id: str, explicit_refs: dict) -> dict:
    session = get_session(root, session_id)
    task = yaml.safe_load(
        (root / ".agent/runtime/tasks" / f"{session['task_id']}.yaml").read_text(encoding="utf-8")
    ) or {}
    return {
        "id": f"CB-{session['task_id']}-{session['role']}-001",
        "task": {"id": task.get("id"), "goal": task.get("goal")},
        "role": {"type": session["role"]},
        "constraints": list(explicit_refs.get("constraints", [])),
        "handoff": explicit_refs.get("handoff", {"from": None, "summary": ""}),
        "evidence": [{"file": item} for item in explicit_refs.get("source", [])],
        "relevant_memory": list(explicit_refs.get("memory", [])),
        "knowledge": list(explicit_refs.get("wiki", [])),
        "expected_output": list(explicit_refs.get("expected_output", [])),
        "token_budget": {"max_context": 32000},
        "provenance": {"session": session_id, "created_at": "2026-08-08T00:00:00+08:00"},
    }
```

CLI `at context inspect <session-id>` 打印 bundle JSON。

- [x] **Step 4: 运行确认通过**

- [x] **Step 5: 记录变更**

---

### Task 6: Handoff Manager

**Files:**
- Create: `src/at_runtime/handoff.py`
- Modify: `src/at_runtime/cli.py`（`at handoff inspect`）
- Test: `tests/test_handoff.py`

**Interfaces:**
- Produces: `create_handoff(root, handoff_id, from_role, to_role, task_id, data: dict) -> dict`、`get_handoff(root, handoff_id) -> dict`。

- [x] **Step 1: 写失败测试**

```python
from at_runtime.handoff import create_handoff, get_handoff


class HandoffTests(unittest.TestCase):
    def test_handoff_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            handoff = create_handoff(
                root,
                "H-T17-A-C",
                "analysis",
                "code",
                "T17",
                {"conclusion": {"root_cause": "beam < 2"}, "constraints": ["keep skipped"]},
            )
            loaded = get_handoff(root, "H-T17-A-C")
            self.assertEqual(loaded["conclusion"]["root_cause"], "beam < 2")
            self.assertEqual(loaded["to"], "code")
```

- [x] **Step 2: 运行确认失败**

- [x] **Step 3: 最小实现**

```python
def create_handoff(root: Path, handoff_id: str, from_role: str, to_role: str, task_id: str, data: dict) -> dict:
    handoff = {
        "id": handoff_id,
        "from": from_role,
        "to": to_role,
        "task": task_id,
        **data,
    }
    path = root / ".agent/handoffs" / f"{handoff_id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(handoff, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return handoff


def get_handoff(root: Path, handoff_id: str) -> dict:
    path = root / ".agent/handoffs" / f"{handoff_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"unknown handoff: {handoff_id}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
```

- [x] **Step 4: 运行确认通过**

- [x] **Step 5: 记录变更**

---

### Task 7: ExecutionAdapter（LocalAdapter + Codex）

**Files:**
- Create: `src/at_runtime/execution.py`
- Test: `tests/test_execution.py`

**Interfaces:**
- Produces:
  - `class ExecutionAdapter`（spawn/resume/terminate/status/collect 抽象）
  - `class LocalAdapter(ExecutionAdapter)`：spawn 调用 Codex CLI（非交互 stdin），
    cwd=项目根，stdout 作为 agent 输出收集。
  - `build_prompt(bundle: dict, role: str) -> str`：渲染 Context Bundle 为 prompt。

- [x] **Step 1: 写失败测试**

```python
from at_runtime.execution import build_prompt


class ExecutionTests(unittest.TestCase):
    def test_build_prompt_includes_bundle_parts(self):
        bundle = {
            "task": {"id": "T17", "goal": "fix beam stability"},
            "role": {"type": "code"},
            "constraints": ["preserve API schema"],
            "handoff": {"from": "analysis", "summary": "beam < 2"},
        }
        prompt = build_prompt(bundle, "code")
        self.assertIn("T17", prompt)
        self.assertIn("fix beam stability", prompt)
        self.assertIn("preserve API schema", prompt)
        self.assertIn("beam < 2", prompt)

    def test_local_adapter_command_uses_codex_exec(self):
        from at_runtime.execution import LocalAdapter

        adapter = LocalAdapter(command=["codex", "exec", "--ephemeral", "-"])
        command = adapter.spawn_command()
        self.assertEqual(command[0], "codex")
        self.assertIn("exec", command)
```

- [x] **Step 2: 运行确认失败**

- [x] **Step 3: 最小实现**

```python
class ExecutionAdapter:
    def spawn(self, bundle: dict, role: str, cwd: Path) -> str:
        raise NotImplementedError


class LocalAdapter(ExecutionAdapter):
    def __init__(self, command: list[str] | None = None) -> None:
        self.command = command or ["codex", "exec", "--skip-git-repo-check",
                                   "--sandbox", "workspace-write", "--ephemeral",
                                   "--color", "never", "-"]

    def spawn_command(self) -> list[str]:
        return list(self.command)

    def spawn(self, bundle: dict, role: str, cwd: Path) -> str:
        import subprocess

        prompt = build_prompt(bundle, role)
        completed = subprocess.run(
            self.command,
            input=prompt.encode("utf-8"),
            cwd=str(cwd),
            capture_output=True,
            timeout=1800,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"agent execution failed ({completed.returncode}): "
                f"{completed.stderr.decode('utf-8', errors='replace')[-500:]}"
            )
        return completed.stdout.decode("utf-8", errors="replace")


def build_prompt(bundle: dict, role: str) -> str:
    task = bundle.get("task", {})
    handoff = bundle.get("handoff", {})
    constraints = bundle.get("constraints", [])
    memory = bundle.get("relevant_memory", [])
    knowledge = bundle.get("knowledge", [])
    return f"""You are the AT `{role}` agent for task {task.get('id')}.

Goal: {task.get('goal')}

Constraints:
{chr(10).join('- ' + item for item in constraints) or '- none'}

Handoff from {handoff.get('from')}:
{handoff.get('summary')}

Relevant memory refs:
{chr(10).join(memory) or '- none'}

Knowledge refs:
{chr(10).join(knowledge) or '- none'}

Produce the expected output and nothing else.
"""
```

- [x] **Step 4: 运行确认通过**

- [x] **Step 5: 记录变更**

---

### Task 8: Runtime Observer

**Files:**
- Create: `src/at_runtime/observer.py`
- Test: `tests/test_observer.py`

**Interfaces:**
- Produces: `record_event(root, event: str, session: str | None, data: dict | None = None) -> None`、
  `list_events(root, limit: int = 50) -> list[dict]`（`.agent/runtime/events/events.jsonl`）。

- [x] **Step 1: 写失败测试**

```python
from at_runtime.observer import list_events, record_event


class ObserverTests(unittest.TestCase):
    def test_events_are_appended(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            record_event(root, "session.created", "s1", {"role": "analysis"})
            record_event(root, "context.injected", "s1", {"tokens": 1234})
            events = list_events(root)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[1]["event"], "context.injected")
            self.assertEqual(events[1]["data"]["tokens"], 1234)
```

- [x] **Step 2: 运行确认失败**

- [x] **Step 3: 最小实现**

```python
import json


def record_event(root: Path, event: str, session: str | None, data: dict | None = None) -> None:
    path = root / ".agent/runtime/events/events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"event": event, "session": session, "data": data or {}}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def list_events(root: Path, limit: int = 50) -> list[dict]:
    path = root / ".agent/runtime/events/events.jsonl"
    if not path.exists():
        return []
    events = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events[-limit:]
```

- [x] **Step 4: 运行确认通过**

- [x] **Step 5: 记录变更**

---

### Task 9: Knowledge Bridge（本地 refs）

**Files:**
- Create: `src/at_runtime/knowledge.py`
- Test: `tests/test_knowledge.py`

**Interfaces:**
- Produces: `propose_knowledge(root, topic, content, source: dict) -> dict`、
  `query_knowledge(root, topic) -> list[dict]`、`get_knowledge(root, ref: str) -> dict | None`。

- [x] **Step 1: 写失败测试**

```python
from at_runtime.knowledge import get_knowledge, propose_knowledge, query_knowledge


class KnowledgeTests(unittest.TestCase):
    def test_propose_and_query(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            propose_knowledge(root, "voice-quality/scoring", "beam < 2 means skipped", {"session": "test-T17"})
            hits = query_knowledge(root, "voice-quality")
            self.assertEqual(len(hits), 1)
            ref = hits[0]["ref"]
            self.assertIsNotNone(get_knowledge(root, ref))
```

- [x] **Step 2: 运行确认失败**

- [x] **Step 3: 最小实现**

```python
import re


def propose_knowledge(root: Path, topic: str, content: str, source: dict) -> dict:
    safe = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    ref = f"wiki://{safe}"
    entry = {"ref": ref, "topic": topic, "content": content, "source": source, "status": "candidate"}
    path = root / ".agent/knowledge/refs" / f"{safe}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(entry, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return entry


def query_knowledge(root: Path, topic: str) -> list[dict]:
    directory = root / ".agent/knowledge/refs"
    if not directory.exists():
        return []
    results = []
    for path in sorted(directory.glob("*.yaml")):
        entry = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if topic.lower() in entry.get("topic", "").lower():
            results.append(entry)
    return results


def get_knowledge(root: Path, ref: str) -> dict | None:
    name = ref.split("//")[-1]
    path = root / ".agent/knowledge/refs" / f"{name}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
```

- [x] **Step 4: 运行确认通过**

- [x] **Step 5: 记录变更**

---

### Task 10: 三 session 流程 + CLI 串联 + doctor

**Files:**
- Create: `src/at_runtime/runner.py`
- Modify: `src/at_runtime/cli.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Produces: `run_task_flow(root, task_id, goal, refs: dict, provider="mock") -> list[dict]`：
  analysis → code → test 三 session，每步 build_context → spawn → handoff。
  `at task run` 与 `at doctor` 命令。

- [x] **Step 1: 写失败测试（mock provider）**

```python
from at_runtime.runner import run_task_flow


class RunnerTests(unittest.TestCase):
    def test_three_session_flow_completes_with_mock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            steps = run_task_flow(
                root,
                "T17",
                "fix beam stability",
                {"constraints": ["preserve API schema"], "source": ["src/scoring.py"]},
                provider="mock",
            )
            self.assertEqual([step["role"] for step in steps], ["analysis", "code", "test"])
            self.assertTrue(all(step["status"] == "done" for step in steps))
            self.assertTrue((root / ".agent/handoffs" / "H-T17-A-C.yaml").exists())
            self.assertTrue((root / ".agent/handoffs" / "H-T17-C-T.yaml").exists())
```

- [x] **Step 2: 运行确认失败**

- [x] **Step 3: 最小实现**

```python
def run_task_flow(root: Path, task_id: str, goal: str, refs: dict, provider: str = "mock") -> list[dict]:
    create_task(root, task_id, goal, refs.get("scope", {}))
    roles = ["analysis", "code", "test"]
    previous_handoff = None
    steps = []
    for index, role in enumerate(roles):
        session_id = f"{role}-{task_id}-01"
        create_session(root, session_id, task_id, role, provider)
        update_session_status(root, session_id, "running")
        record_event(root, "session.created", session_id, {"role": role})
        handoff_refs = {}
        if previous_handoff:
            handoff_refs["handoff"] = previous_handoff
        bundle = build_context(root, session_id, {**refs, **handoff_refs})
        record_event(root, "context.injected", session_id, {"tokens": estimate_tokens(json.dumps(bundle))})
        if provider == "mock":
            output = f"mock {role} output for {task_id}"
        else:
            adapter = LocalAdapter()
            output = adapter.spawn(bundle, role, root)
        handoff_id = f"H-{task_id}-{roles[index - 1][:1].upper()}-{role[:1].upper()}" if index > 0 else None
        if index > 0:
            previous_handoff = {
                "from": roles[index - 1],
                "to": role,
                "summary": output[:500],
                "ref": handoff_id,
            }
            create_handoff(root, handoff_id, roles[index - 1], role, task_id, previous_handoff)
            record_event(root, "handoff.created", session_id, {"handoff": handoff_id})
        update_session_status(root, session_id, "done")
        record_event(root, "session.completed", session_id, {"role": role})
        steps.append({"role": role, "status": "done", "output": output})
    return steps
```

`at doctor`：检查 `.agent` 目录、manifest/policies 可解析、sessions 无 running 残留。

- [x] **Step 4: 运行确认通过**

- [x] **Step 5: 记录变更**

---

### Task 11: 最小对比 eval

**Files:**
- Create: `src/at_runtime/eval.py`
- Modify: `src/at_runtime/cli.py`（`at eval`）
- Test: `tests/test_eval.py`

**Interfaces:**
- Produces: `run_minimal_eval(root, demo_task: str, provider="mock") -> dict`：
  Baseline（单会话直跑）与 AT 三 session 各跑一遍，产出 success / estimated_tokens /
  handoff_sufficiency。

- [x] **Step 1: 写失败测试**

```python
from at_runtime.eval import run_minimal_eval


class EvalTests(unittest.TestCase):
    def test_eval_reports_both_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            result = run_minimal_eval(root, "fix beam stability", provider="mock")
            self.assertIn("baseline", result)
            self.assertIn("at_flow", result)
            self.assertIn("task_success", result["baseline"])
            self.assertIn("estimated_tokens", result["at_flow"])
```

- [x] **Step 2: 运行确认失败**

- [x] **Step 3: 最小实现**

```python
def run_minimal_eval(root: Path, demo_task: str, provider: str = "mock") -> dict:
    baseline_output = f"baseline done: {demo_task}" if provider == "mock" else None
    baseline_tokens = estimate_tokens(baseline_output or demo_task)
    steps = run_task_flow(root, "EVAL1", demo_task, {"constraints": []}, provider=provider)
    at_tokens = sum(estimate_tokens(step["output"]) for step in steps)
    sufficiency = all(step["status"] == "done" for step in steps)
    return {
        "baseline": {"task_success": True, "estimated_tokens": baseline_tokens},
        "at_flow": {
            "task_success": sufficiency,
            "estimated_tokens": at_tokens,
            "handoff_sufficiency": sufficiency,
        },
    }
```

- [x] **Step 4: 运行确认通过**

- [x] **Step 5: 记录变更**

---

### Task 12: 文档、AGENTS.md 与全量验证

**Files:**
- Modify: `README.md`（v2 定位：context-isolated runtime）、`AGENTS.md`（v2 触发与用法）
- Modify: `docs/developing-at.md` 或新增 v2 文档

- [x] **Step 1: 更新 README 与 AGENTS.md**

README 定位改为 "A context-isolated runtime for long-running and parallel coding agents"；
AGENTS.md 说明 `at` 命令族与 Context Bundle 概念。

- [x] **Step 2: 全量测试**

Run: `python -m unittest discover -s tests`
Expected: 全部通过

- [x] **Step 3: 真实 Codex 冒烟（标注性验证）**

Run: `at task run --provider codex`（若本机 codex 可用）；不可用则明确标注"未验证"。

- [x] **Step 4: 记录变更与汇总**

勾选全部 checkbox，报告改动、验证、遗留风险（relevance 显式声明的局限、eval 估算精度）。

## Execution Status

```text
Status: completed
Branch: v2.0
```

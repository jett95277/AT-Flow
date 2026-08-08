# AT v2.1 Memory MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 v2.1 记忆 MVP：三层记忆的树视图、人工操作（promote/archive/discard）、生命线（checkpoint/timeline/rollback）与 checkpoint skill 触发。

**Architecture:** 在现有 V0.1 基础上扩展。`memory.py` 增加状态机操作与跨层迁移；新增 `view.py` 渲染三层树；新增 `timeline.py` 管理生命线快照（全量复制 + 回滚带安全恢复点）；CLI 接入 `at memory` 命令族；`at-memory-checkpoint` skill 用触发词调用 checkpoint。

**Tech Stack:** Python 3.10+（开发验证用 `.venv`，Python 3.12）、PyYAML、标准库（pathlib/shutil/datetime）、unittest。

## Global Constraints

- 规格来源：`docs/superpowers/specs/2026-08-08-at-v2-context-runtime-design.md`（整合版）。
- 核心只做三层记忆 + 可见性 + 人工操作 + 生命线；registry/context/policy/handoff 不再扩展。
- 开发过程中不 commit/push，最后统一提交（沿用 v2.0 惯例）。
- 状态机人工驱动：promotion/清理是人工决策，不做自动 GC/自动提升。
- 快照 = 全量复制（不做 diff）；回滚 = 覆盖恢复且回滚前自动打恢复点。
- 存储：Markdown 正文 + YAML 多文档流元数据；`.agent/` 与 v1 `.at/` 隔离。
- 测试命令统一用 `E:\AT FLOW\.venv\Scripts\python.exe -m unittest <module> -v`，工作目录 `E:\AT FLOW`。

---

### Task 1: Memory 状态机操作（promote / archive / discard）

**Files:**
- Modify: `src/at_runtime/memory.py`
- Test: `tests/test_memory.py`

**Interfaces:**
- Consumes（现有）: `memory_path(root, uri) -> Path`、`write_memory(...)`、
  `read_memory(root, uri) -> list[dict]`、`TIER_DIRS`、`_load_entries(path)`、
  `_save_entries(path, entries)`、`_SAFE_NAME`。
- Produces:
  - `promote_memory(root, uri, to_tier: str | None = None) -> dict`
  - `archive_memory(root, uri) -> dict`
  - `discard_memory(root, uri) -> dict`
  - `list_tier_entries(root, tier, include_all=False) -> list[dict]`（每条含 `uri`）

规则：同层 promote 按 `candidate→active→verified` 升级，`verified` 再 promote
抛 `ValueError`；`--to <tier>` 跨层迁移文件并置 `active`（来源 `verified` 且
目标 `long` 时保持 `verified`）；archive/discard 对文件内全部条目统一置状态。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_memory.py 追加
class MemoryLifecycleTests(unittest.TestCase):
    def _write(self, root, uri, content="finding", **kw):
        write_memory(root, uri, content, source={"session": "s1"}, **kw)

    def test_promote_same_tier_moves_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://task/T17/medium")
            first = promote_memory(root, "memory://task/T17/medium")
            self.assertEqual(first["status"], "active")
            second = promote_memory(root, "memory://task/T17/medium")
            self.assertEqual(second["status"], "verified")
            with self.assertRaises(ValueError):
                promote_memory(root, "memory://task/T17/medium")

    def test_promote_cross_tier_keeps_verified_to_long(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short")
            promote_memory(root, "memory://session/A/short")
            promote_memory(root, "memory://session/A/short")  # candidate→active→verified
            result = promote_memory(root, "memory://session/A/short", to_tier="long")
            self.assertEqual(result["status"], "verified")
            self.assertTrue((root / ".agent/memory/long/session-A.md").exists())
            self.assertFalse((root / ".agent/memory/short/session-A.md").exists())

    def test_promote_cross_tier_medium_from_short(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short")
            result = promote_memory(root, "memory://session/A/short", to_tier="medium")
            self.assertEqual(result["status"], "active")
            self.assertTrue((root / ".agent/memory/medium/session-A.md").exists())
            self.assertFalse((root / ".agent/memory/short/session-A.md").exists())

    def test_archive_and_discard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short")
            archived = archive_memory(root, "memory://session/A/short")
            self.assertEqual(archived["status"], "archived")
            discarded = discard_memory(root, "memory://session/A/short")
            self.assertEqual(discarded["status"], "deprecated")

    def test_list_tier_entries_excludes_inactive_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short", status="candidate")
            self._write(root, "memory://session/B/short", status="archived")
            entries = list_tier_entries(root, "short")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["uri"], "memory://session/A/short")
            self.assertEqual(len(list_tier_entries(root, "short", include_all=True)), 2)
```

文件头导入追加：
`from at_runtime.memory import archive_memory, discard_memory, list_tier_entries, promote_memory`

- [ ] **Step 2: 确认测试失败**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest tests.test_memory -v`
Expected: FAIL —— `ImportError: cannot import name 'promote_memory'`

- [ ] **Step 3: 实现**

```python
# src/at_runtime/memory.py 追加（放在 list_memory 之后）
STATUS_NEXT = {"candidate": "active", "active": "verified"}
INACTIVE = {"archived", "deprecated"}


def _parse_uri(uri: str) -> tuple[str, str, str]:
    parts = uri.split("/")
    if len(parts) < 5:
        raise ValueError(f"invalid memory uri: {uri}")
    scope, name, tier = parts[2], parts[3], parts[4]
    if tier not in TIER_DIRS:
        raise ValueError(f"unknown tier: {tier}")
    if not _SAFE_NAME.fullmatch(scope) or not _SAFE_NAME.fullmatch(name):
        raise ValueError(f"invalid memory uri: {uri}")
    return scope, name, tier


def list_tier_entries(
    root: Path, tier: str, include_all: bool = False
) -> list[dict[str, Any]]:
    directory = root / ".agent" / TIER_DIRS[tier]
    if not directory.exists():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.md")):
        for entry in _load_entries(path):
            if include_all or entry.get("status") not in INACTIVE:
                entries.append(entry)
    return entries


def _update_entries(root: Path, uri: str, status: str | None = None,
                    to_tier: str | None = None) -> dict[str, Any]:
    scope, name, tier = _parse_uri(uri)
    path = memory_path(root, uri)
    if not path.exists():
        raise FileNotFoundError(f"unknown memory: {uri}")
    entries = _load_entries(path)
    if not entries:
        raise ValueError(f"empty memory: {uri}")
    if to_tier:
        if to_tier not in TIER_DIRS:
            raise ValueError(f"unknown tier: {to_tier}")
        for entry in entries:
            entry["status"] = (
                "verified"
                if entry["status"] == "verified" and to_tier == "long"
                else "active"
            )
        new_uri = f"memory://{scope}/{name}/{to_tier}"
        new_path = memory_path(root, new_uri)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if new_path.exists():
            entries = _load_entries(new_path) + entries
        _save_entries(new_path, entries)
        path.unlink()
        return entries[-1]
    if status:
        for entry in entries:
            entry["status"] = status
        _save_entries(path, entries)
        return entries[-1]
    raise ValueError("nothing to do")


def promote_memory(root: Path, uri: str, to_tier: str | None = None) -> dict[str, Any]:
    if to_tier:
        return _update_entries(root, uri, to_tier=to_tier)
    scope, name, tier = _parse_uri(uri)
    path = memory_path(root, uri)
    if not path.exists():
        raise FileNotFoundError(f"unknown memory: {uri}")
    entries = _load_entries(path)
    if not entries:
        raise ValueError(f"empty memory: {uri}")
    current = entries[-1]["status"]
    if current not in STATUS_NEXT:
        raise ValueError(f"cannot promote status {current!r}")
    entries[-1]["status"] = STATUS_NEXT[current]
    _save_entries(path, entries)
    return entries[-1]


def archive_memory(root: Path, uri: str) -> dict[str, Any]:
    return _update_entries(root, uri, status="archived")


def discard_memory(root: Path, uri: str) -> dict[str, Any]:
    return _update_entries(root, uri, status="deprecated")
```

同时把 `memory_path` 改为复用 `_parse_uri`（保持行为不变）：

```python
def memory_path(root: Path, uri: str) -> Path:
    scope, name, tier = _parse_uri(uri)
    return root / ".agent" / TIER_DIRS[tier] / f"{scope}-{name}.md"
```

- [ ] **Step 4: 确认测试通过**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest tests.test_memory -v`
Expected: PASS（原 5 个 + 新增 5 个，共 10 个）

- [ ] **Step 5: 记录变更（不 commit，最后统一提交）**

---

### Task 2: 树视图 + CLI 接线

**Files:**
- Create: `src/at_runtime/view.py`
- Modify: `src/at_runtime/cli.py`
- Test: `tests/test_view.py`

**Interfaces:**
- Consumes: `list_tier_entries(root, tier, include_all=False) -> list[dict]`（Task 1）
- Produces: `render_memory_tree(root, include_all=False) -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_view.py
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.memory import write_memory
from at_runtime.view import render_memory_tree
from at_runtime.workspace import initialize_workspace


class ViewTests(unittest.TestCase):
    def test_tree_shows_three_tiers_and_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory(root, "memory://session/A/short", "short note",
                         source={"session": "A"})
            write_memory(root, "memory://task/T17/medium", "root cause",
                         source={"session": "code-T17"})
            tree = render_memory_tree(root)
            self.assertIn("memory", tree)
            self.assertIn("short", tree)
            self.assertIn("medium", tree)
            self.assertIn("long", tree)
            self.assertIn("session-A", tree)
            self.assertIn("task-T17", tree)
            self.assertIn("short note", tree)
            self.assertIn("root cause", tree)

    def test_tree_hides_inactive_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory(root, "memory://session/A/short", "hidden",
                         source={"session": "A"}, status="archived")
            self.assertNotIn("hidden", render_memory_tree(root))
            self.assertIn("hidden", render_memory_tree(root, include_all=True))
```

- [ ] **Step 2: 确认测试失败**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest tests.test_view -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'at_runtime.view'`

- [ ] **Step 3: 实现**

```python
# src/at_runtime/view.py
from __future__ import annotations

from pathlib import Path

from at_runtime.memory import TIER_DIRS, list_tier_entries


def render_memory_tree(root: Path, include_all: bool = False) -> str:
    lines = ["memory"]
    for index, tier in enumerate(("short", "medium", "long")):
        branch = "└──" if index == 2 else "├──"
        lines.append(f"{branch} {tier}")
        by_name: dict[str, list[dict]] = {}
        for entry in list_tier_entries(root, tier, include_all=include_all):
            uri = entry.get("uri", "")
            parts = uri.split("/")
            name = f"{parts[2]}-{parts[3]}" if len(parts) >= 5 else "unknown"
            by_name.setdefault(name, []).append(entry)
        for name_index, (name, entries) in enumerate(sorted(by_name.items())):
            name_branch = "└──" if name_index == len(by_name) - 1 else "├──"
            lines.append(f"│   {name_branch} {name}")
            for entry in entries:
                status = entry.get("status", "candidate")
                content = (entry.get("content", "") or "").splitlines()[0][:50]
                source = str(entry.get("source", ""))
                created = entry.get("created_at", "")[:16]
                lines.append(
                    f"│   │   └── [{status}] {content} · {source} · {created}"
                )
    return "\n".join(lines)
```

`cli.py` 的 `memory` 子命令扩展为：

```python
    memory_parser = subparsers.add_parser("memory", help="inspect and manage memory")
    memory_sub = memory_parser.add_subparsers(dest="memory_command", required=True)
    inspect = memory_sub.add_parser("inspect", help="show memory entries for a uri")
    inspect.add_argument("uri", help="memory://<scope>/<name>/<tier>")
    view = memory_sub.add_parser("view", help="show memory tree")
    view.add_argument("--all", action="store_true", help="include archived/deprecated")
    promote = memory_sub.add_parser("promote", help="promote memory entry")
    promote.add_argument("uri")
    promote.add_argument("--to", choices=["medium", "long"], default=None,
                         help="move to another tier")
    archive = memory_sub.add_parser("archive", help="archive memory entry")
    archive.add_argument("uri")
    discard = memory_sub.add_parser("discard", help="discard memory entry")
    discard.add_argument("uri")
```

`main()` 内 `memory` 分支改为：

```python
    if args.command == "memory":
        root = Path.cwd()
        if args.memory_command == "inspect":
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
```

`cli.py` 导入追加：
`from at_runtime.memory import archive_memory, discard_memory, promote_memory, read_memory`
`from at_runtime.view import render_memory_tree`

- [ ] **Step 4: 确认测试通过**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest tests.test_view tests.test_memory -v`
Expected: PASS

- [ ] **Step 5: 记录变更（不 commit，最后统一提交）**

---

### Task 3: 生命线（checkpoint / timeline / rollback）

**Files:**
- Create: `src/at_runtime/timeline.py`
- Modify: `src/at_runtime/cli.py`
- Test: `tests/test_timeline.py`

**Interfaces:**
- Consumes: `TIER_DIRS`（memory.py）、`record_event(root, event, session, data)`
  （observer.py）
- Produces:
  - `create_checkpoint(root, label: str) -> dict`
  - `list_checkpoints(root) -> list[dict]`
  - `rollback_memory(root, node_id: str) -> dict`

规则：checkpoint 把 `.agent/memory/{short,medium,long}` 全量复制到
`.agent/timeline/<ts>-<label>/memory/`，写 `meta.yaml`（id/label/created_at/
各层条目数）；rollback 先自动打 `pre-rollback-<node>` 恢复点，再清空
`.agent/memory` 各层并复制节点快照回来。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_timeline.py
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.memory import read_memory, write_memory
from at_runtime.timeline import create_checkpoint, list_checkpoints, rollback_memory
from at_runtime.workspace import initialize_workspace


class TimelineTests(unittest.TestCase):
    def test_checkpoint_and_list(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory(root, "memory://session/A/short", "note",
                         source={"session": "A"})
            node = create_checkpoint(root, "fix beam stability")
            self.assertTrue(node["id"].endswith("fix-beam-stability"))
            checkpoints = list_checkpoints(root)
            self.assertEqual(len(checkpoints), 1)
            self.assertEqual(checkpoints[0]["label"], "fix beam stability")

    def test_rollback_restores_memory_and_creates_recovery_point(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory(root, "memory://session/A/short", "original",
                         source={"session": "A"})
            node = create_checkpoint(root, "before-change")
            write_memory(root, "memory://session/A/short", "changed",
                         source={"session": "A"})
            rollback_memory(root, node["id"])
            entries = read_memory(root, "memory://session/A/short")
            self.assertEqual(entries[-1]["content"], "original")
            checkpoints = list_checkpoints(root)
            self.assertEqual(len(checkpoints), 2)  # 原节点 + 自动恢复点
            self.assertTrue(checkpoints[0]["label"].startswith("pre-rollback"))
```

- [ ] **Step 2: 确认测试失败**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest tests.test_timeline -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'at_runtime.timeline'`

- [ ] **Step 3: 实现**

```python
# src/at_runtime/timeline.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
from typing import Any

import yaml

from at_runtime.memory import TIER_DIRS
from at_runtime.observer import record_event


def _safe_label(label: str) -> str:
    safe = re.sub(r"[^a-z0-9_-]+", "-", label.lower()).strip("-")
    return safe or "checkpoint"


def create_checkpoint(root: Path, label: str) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    node_id = f"{ts}-{_safe_label(label)}"
    node_dir = root / ".agent/timeline" / node_id
    memory_dir = node_dir / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    tier_counts: dict[str, int] = {}
    for tier, relative in TIER_DIRS.items():
        source = root / ".agent" / relative
        if source.exists():
            shutil.copytree(source, memory_dir / tier)
            tier_counts[tier] = len(list(source.glob("*.md")))
    meta = {
        "id": node_id,
        "label": label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tiers": tier_counts,
    }
    (node_dir / "meta.yaml").write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    record_event(root, "memory.checkpoint", None, {"node": node_id})
    return meta


def list_checkpoints(root: Path) -> list[dict[str, Any]]:
    directory = root / ".agent/timeline"
    if not directory.exists():
        return []
    nodes = []
    for path in sorted(directory.glob("*/meta.yaml"), reverse=True):
        nodes.append(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return nodes


def rollback_memory(root: Path, node_id: str) -> dict[str, Any]:
    node_dir = root / ".agent/timeline" / node_id
    if not node_dir.exists():
        raise FileNotFoundError(f"unknown checkpoint: {node_id}")
    create_checkpoint(root, f"pre-rollback-{node_id}")
    for tier, relative in TIER_DIRS.items():
        target = root / ".agent" / relative
        target.mkdir(parents=True, exist_ok=True)
        for path in target.glob("*"):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        source = node_dir / "memory" / tier
        if source.exists():
            shutil.copytree(source, target, dirs_exist_ok=True)
    record_event(root, "memory.rollback", None, {"node": node_id})
    return {"node": node_id, "rolled_back": True}
```

`cli.py` 追加三个子命令与分支（沿用 Task 2 的 memory 子命令结构）：

```python
    checkpoint = memory_sub.add_parser("checkpoint", help="create memory checkpoint")
    checkpoint.add_argument("label", help="checkpoint label")
    memory_sub.add_parser("timeline", help="list checkpoints")
    rollback = memory_sub.add_parser("rollback", help="rollback memory to checkpoint")
    rollback.add_argument("node", help="checkpoint id (from timeline)")
```

`main()` 内追加：

```python
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
```

`cli.py` 导入追加：
`from at_runtime.timeline import create_checkpoint, list_checkpoints, rollback_memory`

- [ ] **Step 4: 确认测试通过**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest tests.test_timeline -v`
Expected: PASS（2 个用例）

- [ ] **Step 5: 记录变更（不 commit，最后统一提交）**

---

### Task 4: checkpoint skill（触发词触发）

**Files:**
- Create: `C:\Users\kk\.codex\skills\at-memory-checkpoint\SKILL.md`
- Create: `C:\Users\kk\.codex\skills\at-memory-checkpoint\agents\openai.yaml`

**前置：** 写权限——`C:\Users\kk\.codex\skills` 不在工作区写权限内，创建前需要
用户批准一次写权限。

- [ ] **Step 1: 初始化 skill**

Run:
`python "C:\Users\kk\.codex\skills\.system\skill-creator\scripts\init_skill.py" at-memory-checkpoint --path "C:\Users\kk\.codex\skills" --interface display_name="AT Memory Checkpoint" --interface short_description="Trigger-word checkpoint for AT three-tier memory timeline" --interface default_prompt="打点"`

Expected: 生成 skill 目录与 SKILL.md 模板

- [ ] **Step 2: 写 SKILL.md**

```markdown
---
name: at-memory-checkpoint
description: Record an AT runtime memory timeline checkpoint. Use when the user says "打点", "记录时间节点", "存个档", "checkpoint", or otherwise asks to save a development milestone / time node in the AT three-tier memory. Triggers `at memory checkpoint`.
---

Run the AT CLI from the project root:

```powershell
python "E:\AT FLOW\.venv\Scripts\at.exe" memory checkpoint "<label>"
```

Label: derive a short label from the user's milestone (e.g. "fix beam stability").
If the user gave no milestone, label the checkpoint with the current stage name.
Show the returned checkpoint JSON to the user.
```

- [ ] **Step 3: 验证 skill**

Run:
`python "C:\Users\kk\.codex\skills\.system\skill-creator\scripts\quick_validate.py" "C:\Users\kk\.codex\skills\at-memory-checkpoint"`
Expected: validation passed

- [ ] **Step 4: 端到端触发验证（手工标注）**

在 `E:\AT FLOW` 临时目录初始化 `.agent`，写入一条 memory，然后模拟触发：
Run: `E:\AT FLOW\.venv\Scripts\at.exe memory checkpoint "manual-trigger"`
Expected: 生成 `timeline/<ts>-manual-trigger/` 与 meta.yaml；随后
`at memory timeline` 能列出该节点。

- [ ] **Step 5: 记录变更（不 commit，最后统一提交）**

---

### Task 5: 文档与全量验证

**Files:**
- Modify: `README.md`（快速开始补 `at memory` 命令族）
- Modify: `AGENTS.md`（补 memory 命令映射与触发词）

- [ ] **Step 1: 更新 README 快速开始**

在快速开始段落追加：

```powershell
# 查看三层记忆树 / 人工操作 / 生命线
.venv\Scripts\at memory view
.venv\Scripts\at memory promote memory://task/T17/medium
.venv\Scripts\at memory checkpoint "fix beam stability"
.venv\Scripts\at memory timeline
```

- [ ] **Step 2: 更新 AGENTS.md 命令映射**

`## Command Mapping (v2)` 追加：

- `AT: memory view` -> `python "E:\AT FLOW\.venv\Scripts\at.exe" memory view`
- `AT: memory promote, <memory-uri>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" memory promote <memory-uri>`
- `AT: memory checkpoint, <label>` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" memory checkpoint <label>`
- `AT: memory timeline` -> `python "E:\AT FLOW\.venv\Scripts\at.exe" memory timeline`

并在触发规则说明：用户说"打点 / 记录时间节点 / 存个档"时，调用
`at-memory-checkpoint` skill 执行 checkpoint。

- [ ] **Step 3: 全量测试**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest discover -s tests`
Expected: 全部通过（原 24 + 新增 9 = 33 个）

- [ ] **Step 4: 真实冒烟**

在临时目录：`at init` → `at memory view` → 写 memory → `at memory checkpoint`
→ `at memory timeline` → `at memory rollback`，确认命令族端到端可用。

- [ ] **Step 5: 汇总记录（不 commit，最后统一提交）**

---

## Execution Status

```text
Status: in progress
Branch: v2.0
```

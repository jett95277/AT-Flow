# AT v2.2 Export Verification Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 `at memory export`：把三层记忆导出为一份人类可读的 Markdown 报告（默认 `.agent/export/memory-<ts>.md`，支持 `--stdout` 与 `--all`），同时作为 v2.2 Superpowers 工作流（writing-plans → executing-plans → 阶段记忆沉淀）的真实验证样本。

**Architecture:** 导出是"渲染"类能力，与树视图同属展示层。`view.py` 增加 `render_memory_export(root, include_all=False) -> str` 生成 Markdown；`cli.py` 增加 `at memory export` 子命令，默认写文件、`--stdout` 输出到控制台。不改 memory 核心。

**Tech Stack:** Python 3.10+（`.venv` Python 3.12）、标准库（datetime/pathlib）、unittest。

## Global Constraints

- 规格来源：`docs/superpowers/specs/2026-08-08-at-v2-context-runtime-design.md`（记忆层版）。
- 不改 `memory.py` 核心；导出只读，不做任何写入/状态变更。
- 复用现有 `list_tier_entries(root, tier, include_all)` 读取条目。
- 开发中每个任务本地 commit（不 push），全部完成后统一 push。
- 测试命令统一用 `E:\AT FLOW\.venv\Scripts\python.exe -m unittest <module> -v`，工作目录 `E:\AT FLOW`。
- 验证工作流：每完成一个任务，用 `at memory write` 沉淀阶段结论（`--task V22P`）。

---

### Task 1: 导出渲染函数 render_memory_export

**Files:**
- Modify: `src/at_runtime/view.py`
- Test: `tests/test_view.py`

**Interfaces:**
- Consumes: `list_tier_entries(root, tier, include_all=False) -> list[dict]`（已存在）
- Produces: `render_memory_export(root, include_all=False) -> str`

输出 Markdown 结构：`# AT Memory Export`、生成时间、`## short / medium / long`
三节，每节按 `<scope>-<name>` 分组，条目含 `[status] content`、constraints、
unresolved、source、created_at。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_view.py 追加
class ExportTests(unittest.TestCase):
    def test_export_contains_tiers_and_entry_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(
                root,
                "memory://task/T17/medium",
                conclusion="root cause",
                constraints=["keep schema"],
                unresolved=["threshold?"],
                source={"project": "P"},
            )
            report = render_memory_export(root)
            self.assertIn("# AT Memory Export", report)
            self.assertIn("## short", report)
            self.assertIn("## medium", report)
            self.assertIn("## long", report)
            self.assertIn("root cause", report)
            self.assertIn("keep schema", report)
            self.assertIn("threshold?", report)
            self.assertIn("task-T17", report)

    def test_export_hides_inactive_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://session/A/short", conclusion="hidden")
            archive_memory(root, "memory://session/A/short")
            self.assertNotIn("hidden", render_memory_export(root))
            self.assertIn("hidden", render_memory_export(root, include_all=True))
```

文件头导入追加：
`from at_runtime.view import render_memory_export`

- [ ] **Step 2: 确认测试失败**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest tests.test_view -v`
Expected: FAIL —— `ImportError: cannot import name 'render_memory_export'`

- [ ] **Step 3: 实现**

```python
# src/at_runtime/view.py 追加
from datetime import datetime, timezone


def render_memory_export(root: Path, include_all: bool = False) -> str:
    lines = [
        "# AT Memory Export",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for tier in ("short", "medium", "long"):
        lines.append(f"## {tier}")
        lines.append("")
        entries = list_tier_entries(root, tier, include_all=include_all)
        by_name: dict[str, list[dict]] = {}
        for entry in entries:
            parts = entry.get("uri", "").split("/")
            name = f"{parts[2]}-{parts[3]}" if len(parts) >= 5 else "unknown"
            by_name.setdefault(name, []).append(entry)
        if not by_name:
            lines.append("_(empty)_")
            lines.append("")
            continue
        for name, name_entries in sorted(by_name.items()):
            lines.append(f"### {name}")
            for entry in name_entries:
                status = entry.get("status", "candidate")
                content = entry.get("content", "") or ""
                lines.append(f"- [{status}] {content}")
                for label, key in (("Constraints", "constraints"),
                                   ("Unresolved", "unresolved")):
                    items = entry.get(key) or []
                    if items:
                        lines.append(f"  {label}:")
                        for item in items:
                            lines.append(f"    - {item}")
                source = entry.get("source") or {}
                created = entry.get("created_at", "")
                lines.append(f"  Source: {source} | Created: {created}")
            lines.append("")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: 确认测试通过**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest tests.test_view -v`
Expected: PASS（ViewTests 3 + CliMemoryTests 1 + ExportTests 2）

- [ ] **Step 5: Commit + 沉淀阶段记忆**

```bash
git add tests/test_view.py src/at_runtime/view.py
git commit -m "feat: add memory export renderer"
E:\AT FLOW\.venv\Scripts\at.exe memory write memory://session/impl-V22P/short --conclusion "render_memory_export 完成，Markdown 报告含三层/字段" --task V22P
```

---

### Task 2: CLI at memory export

**Files:**
- Modify: `src/at_runtime/cli.py`
- Test: `tests/test_view.py`

**Interfaces:**
- Consumes: `render_memory_export(root, include_all=False) -> str`（Task 1）
- Produces: `at memory export [--out PATH] [--stdout] [--all]`

规则：无 `--stdout` 时写入 `.agent/export/memory-<ts>.md`（ts 为本地时间
`%Y%m%dT%H%M%S`）并打印路径；`--out PATH` 指定输出文件；`--stdout` 直接
打印报告到控制台。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_view.py 追加
class CliExportTests(unittest.TestCase):
    def test_cli_export_writes_file(self):
        from at_runtime.cli import main
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://task/T17/medium",
                                    conclusion="root cause")
            old = os.getcwd()
            os.chdir(root)
            try:
                code = main(["memory", "export"])
            finally:
                os.chdir(old)
            self.assertEqual(code, 0)
            exports = list((root / ".agent/export").glob("memory-*.md"))
            self.assertEqual(len(exports), 1)
            self.assertIn("root cause", exports[0].read_text(encoding="utf-8"))
```

- [ ] **Step 2: 确认测试失败**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest tests.test_view -v`
Expected: FAIL —— CLI 无 export 子命令（argparse 报错）

- [ ] **Step 3: 实现**

```python
# src/at_runtime/cli.py：memory 子命令追加
    export = memory_sub.add_parser("export", help="export memory as markdown report")
    export.add_argument("--out", default=None, help="output file path")
    export.add_argument("--stdout", action="store_true", help="print report to stdout")
    export.add_argument("--all", action="store_true",
                        help="include archived/deprecated entries")
```

`main()` 内 memory 分支追加：

```python
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
```

`cli.py` 导入追加：`from datetime import datetime`、
`from at_runtime.view import render_memory_export`。

- [ ] **Step 4: 确认测试通过**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest tests.test_view -v`
Expected: PASS

- [ ] **Step 5: Commit + 沉淀阶段记忆**

```bash
git add tests/test_view.py src/at_runtime/cli.py
git commit -m "feat: add at memory export CLI"
E:\AT FLOW\.venv\Scripts\at.exe memory write memory://session/impl-V22P/short --conclusion "at memory export CLI 完成（文件/--stdout/--all）" --task V22P
```

---

### Task 3: 文档 + 全量验证 + 打点

**Files:**
- Modify: `README.md`（快速开始补 export）
- Modify: `AGENTS.md`（命令映射补 export）

- [ ] **Step 1: 更新 README 快速开始**

在记忆命令族段落追加：

```powershell
# 导出三层记忆为 Markdown 报告
.venv\Scripts\at memory export
```

- [ ] **Step 2: 更新 AGENTS.md 命令映射**

追加：

- `AT: memory export` ->
  `python "E:\AT FLOW\.venv\Scripts\at.exe" memory export`

- [ ] **Step 3: 全量测试**

Run: `E:\AT FLOW\.venv\Scripts\python.exe -m unittest discover -s tests`
Expected: 全部通过（45 个）

- [ ] **Step 4: 真实冒烟 + 打点**

```bash
E:\AT FLOW\.venv\Scripts\at.exe memory export --stdout | Select-Object -First 8
E:\AT FLOW\.venv\Scripts\at.exe memory export
E:\AT FLOW\.venv\Scripts\at.exe memory checkpoint "v22p-export完成"
```

- [ ] **Step 5: Commit + 沉淀**

```bash
git add README.md AGENTS.md
git commit -m "docs: add memory export to README and AGENTS"
E:\AT FLOW\.venv\Scripts\at.exe memory write memory://session/impl-V22P/short --conclusion "at memory export 交付完成，工作流闭环验证通过" --task V22P
```

---

## Execution Status

```text
Status: completed
Branch: v2.1
```

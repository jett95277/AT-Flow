from pathlib import Path
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot_memory.cli import main
from xiaot_memory.workspace import initialize_workspace


def _run(root, argv):
    old = os.getcwd()
    os.chdir(root)
    try:
        return main(argv)
    finally:
        os.chdir(old)


class CliGovernanceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        initialize_workspace(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    # short 无 task 准入失败
    def test_add_short_without_task_fails(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = _run(
                self.root,
                ["memory", "add", "memory://session/A/short", "--conclusion", "x"],
            )
        self.assertEqual(code, 1)
        self.assertIn("SHORT_REQUIRES_TASK", err.getvalue())

    # short 带 task 准入成功
    def test_add_short_with_task_ok(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = _run(
                self.root,
                ["memory", "add", "memory://session/A/short",
                 "--conclusion", "beam 阈值", "--task", "T1"],
            )
        self.assertEqual(code, 0)
        item = json.loads(buf.getvalue())
        self.assertEqual(item["tier"], "short")
        self.assertEqual(item["task_id"], "T1")

    # 项目级约束 + 确认可直接写 medium
    def test_add_project_constraint_ok(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = _run(
                self.root,
                ["memory", "add", "memory://project/ASR/medium",
                 "--conclusion", "保持 schema 不变", "--kind", "constraint",
                 "--confirmed"],
            )
        self.assertEqual(code, 0)
        item = json.loads(buf.getvalue())
        self.assertEqual(item["scope"], "project")
        self.assertEqual(item["kind"], "constraint")

    # 完整链路 add -> verify -> promote --confirmed --evidence --distilled
    def test_verify_promote_flow(self):
        _run(self.root, ["memory", "add", "memory://session/A/short",
                         "--conclusion", "beam 阈值 2", "--task", "T1"])
        _run(self.root, ["memory", "verify", "memory://session/A/short",
                         "--evidence", "test:beam<2"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = _run(
                self.root,
                ["memory", "promote", "memory://session/A/short", "--to", "medium",
                 "--confirmed", "--evidence", "test:beam<2",
                 "--distilled", "beam 阈值固定为 2"],
            )
        self.assertEqual(code, 0)
        item = json.loads(buf.getvalue())
        self.assertEqual(item["tier"], "medium")
        self.assertEqual(item["content"], "beam 阈值固定为 2")
        self.assertTrue((self.root / ".agent/memory/medium/task-T1.md").exists())

    # promote 未确认失败（严格路径）
    def test_promote_without_confirmed_fails(self):
        _run(self.root, ["memory", "add", "memory://session/A/short",
                         "--conclusion", "beam 阈值 2", "--task", "T1"])
        _run(self.root, ["memory", "verify", "memory://session/A/short",
                         "--evidence", "test:beam<2"])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = _run(
                self.root,
                ["memory", "promote", "memory://session/A/short", "--to", "medium",
                 "--evidence", "test:beam<2", "--distilled", "beam 阈值固定为 2"],
            )
        self.assertEqual(code, 1)
        self.assertIn("REQUIRES_CONFIRMATION", err.getvalue())

    # settle 默认 dry-run
    def test_settle_dry_run(self):
        _run(self.root, ["memory", "add", "memory://session/A/short",
                         "--conclusion", "beam 阈值 2", "--task", "T1"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = _run(self.root, ["memory", "settle", "T1"])
        self.assertEqual(code, 0)
        result = json.loads(buf.getvalue())
        self.assertTrue(result["dry_run"])
        self.assertEqual(len(result["keep"]), 1)

    # memory context 显示治理上下文
    def test_memory_context_shows_entries(self):
        _run(self.root, ["memory", "add", "memory://session/A/short",
                         "--conclusion", "beam 阈值 2", "--task", "T1"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = _run(self.root, ["memory", "context", "memory://session/A/short"])
        self.assertEqual(code, 0)
        ctx = json.loads(buf.getvalue())
        self.assertEqual(ctx["uris"], ["memory://session/A/short"])
        self.assertEqual(len(ctx["entries"]["memory://session/A/short"]), 1)

    # memory events 记录治理操作
    def test_memory_events_listed(self):
        _run(self.root, ["memory", "add", "memory://session/A/short",
                         "--conclusion", "x", "--task", "T1"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = _run(self.root, ["memory", "events"])
        self.assertEqual(code, 0)
        events = json.loads(buf.getvalue())
        self.assertTrue(any(e.get("event") == "memory.create" for e in events))


if __name__ == "__main__":
    unittest.main()

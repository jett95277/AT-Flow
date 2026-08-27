from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot_memory.memory import memory_path, read_memory, write_memory, write_memory_structured
from xiaot_memory.memory_models import hydrate_entry, make_entry
from xiaot_memory.memory_settle import apply_confirmed, classify_entries, settle_task
from xiaot_memory.workspace import initialize_workspace


class SettleRoot:
    """临时仓库根上下文管理器。"""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        initialize_workspace(self.root)

    def __enter__(self):
        return self.root

    def __exit__(self, *exc):
        self._tmp.cleanup()


def _write_process_short(root, uri, content, source):
    """写入一条 kind=process 的 short（模拟纯过程记录，不走治理准入）。"""
    entry = make_entry(uri, content, source, kind="process")
    path = memory_path(root, uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump_all([entry], allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _snapshot(root, uri):
    path = memory_path(root, uri)
    return path.read_text(encoding="utf-8") if path.exists() else None


class TestSettle(unittest.TestCase):
    # 场景 10：settle 默认 dry-run，不写盘
    def test_settle_dry_run_does_not_write(self):
        with SettleRoot() as root:
            write_memory(root, "memory://session/A/short", "结论A", {"task": "T1"})
            write_memory(root, "memory://session/A/short", "结论B", {"task": "T1"})
            before = _snapshot(root, "memory://session/A/short")
            result = settle_task(root, "T1")
            self.assertTrue(result["dry_run"])
            self.assertEqual(_snapshot(root, "memory://session/A/short"), before)

    # 场景 11：unresolved 的 short 结算后保留
    def test_settle_unresolved_retained(self):
        with SettleRoot() as root:
            write_memory_structured(
                root, "memory://session/A/short",
                conclusion="问题诊断中",
                unresolved=["如何复现", "根因未知"],
                source={"task": "T1"},
            )
            result = settle_task(root, "T1")
            self.assertEqual(result["auto_archive"], [])
            self.assertEqual(len(result["keep"]), 1)
            # apply 也不归档 unresolved
            applied = settle_task(root, "T1", dry_run=False)
            self.assertEqual(applied["auto_archived"], [])
            entries = read_memory(root, "memory://session/A/short")
            self.assertEqual(len(entries), 1)
            self.assertEqual(hydrate_entry(entries[0])["validity"], "current")

    # 场景 12：纯过程记录可自动归档，普通结论保留
    def test_settle_process_info_archived(self):
        with SettleRoot() as root:
            _write_process_short(root, "memory://session/A/short", "运行了迁移脚本", {"task": "T1"})
            write_memory(root, "memory://session/A/short", "beam 阈值 2", {"task": "T1"})
            result = settle_task(root, "T1", dry_run=True)
            self.assertEqual(len(result["auto_archive"]), 1)
            self.assertEqual(len(result["keep"]), 1)
            # apply 只自动归档过程记录
            applied = settle_task(root, "T1", dry_run=False)
            self.assertEqual(len(applied["auto_archived"]), 1)
            entries = read_memory(root, "memory://session/A/short")
            by_content = {hydrate_entry(e)["content"]: hydrate_entry(e) for e in entries}
            self.assertEqual(by_content["运行了迁移脚本"]["validity"], "archived")
            self.assertEqual(by_content["beam 阈值 2"]["validity"], "current")

    # 场景 13a：重复内容只在 suggest_discard，apply 不自动 discard
    def test_settle_duplicate_not_auto_discarded(self):
        with SettleRoot() as root:
            write_memory(root, "memory://session/A/short", "重复结论", {"task": "T1"})
            write_memory(root, "memory://session/A/short", "重复结论", {"task": "T1"})
            result = settle_task(root, "T1", dry_run=True)
            self.assertEqual(len(result["suggest_discard"]), 1)
            applied = settle_task(root, "T1", dry_run=False)
            self.assertEqual(applied["auto_archived"], [])
            for entry in read_memory(root, "memory://session/A/short"):
                self.assertEqual(hydrate_entry(entry)["validity"], "current")

    # 场景 13b：discard 需用户确认，apply_confirmed 后置 discarded
    def test_apply_confirmed_discards(self):
        with SettleRoot() as root:
            write_memory(root, "memory://session/A/short", "重复结论", {"task": "T1"})
            write_memory(root, "memory://session/A/short", "重复结论", {"task": "T1"})
            settle_task(root, "T1", dry_run=True)
            dup_id = hydrate_entry(read_memory(root, "memory://session/A/short")[1])["id"]
            applied = apply_confirmed(root, "T1", discard_ids=[dup_id])
            self.assertEqual(applied["discarded"], [dup_id])
            by_id = {
                hydrate_entry(e)["id"]: hydrate_entry(e)
                for e in read_memory(root, "memory://session/A/short")
            }
            self.assertEqual(by_id[dup_id]["validity"], "discarded")


class TestClassify(unittest.TestCase):
    def test_duplicate_classified_as_discard(self):
        with SettleRoot() as root:
            write_memory(root, "memory://session/A/short", "同内容", {"task": "T1"})
            write_memory(root, "memory://session/A/short", "同内容", {"task": "T1"})
            entries = read_memory(root, "memory://session/A/short")
            classified = classify_entries(entries, task_completed=True)
            self.assertEqual(len(classified["suggest_discard"]), 1)
            self.assertEqual(len(classified["keep"]), 1)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot_memory.memory import (
    archive_memory,
    discard_memory,
    list_tier_entries,
    memory_path,
    promote_memory,
    read_memory,
    write_memory,
    write_memory_structured,
)
from xiaot_memory.workspace import initialize_workspace


class MemoryTests(unittest.TestCase):
    def test_memory_uri_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            path = memory_path(root, "memory://session/S32/short")
            self.assertEqual(
                path.relative_to(root).as_posix(),
                ".agent/memory/short/session-S32.md",
            )

    def test_short_memory_is_session_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory(
                root,
                "memory://session/A/short",
                "analysis finding",
                source={"session": "A"},
            )
            self.assertEqual(len(read_memory(root, "memory://session/B/short")), 0)
            self.assertEqual(len(read_memory(root, "memory://session/A/short")), 1)

    def test_long_memory_is_project_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory(
                root,
                "memory://project/ASR/long",
                "stable fact",
                source={"session": "code-T17"},
            )
            self.assertEqual(len(read_memory(root, "memory://project/ASR/long")), 1)

    def test_roundtrip_preserves_multiline_content_and_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory(
                root,
                "memory://session/A/short",
                "first line\nsecond line\nnote: keep me",
                source={"session": "A", "handoff": "H-T17-A-C"},
                status="candidate",
            )
            entries = read_memory(root, "memory://session/A/short")
            self.assertEqual(len(entries), 1)
            entry = entries[0]
            self.assertEqual(entry["content"], "first line\nsecond line\nnote: keep me")
            self.assertEqual(entry["source"], {"session": "A", "handoff": "H-T17-A-C"})
            self.assertEqual(entry["status"], "candidate")
            self.assertNotEqual(entry["created_at"], "2026-08-08T00:00:00+08:00")

    def test_memory_uri_rejects_unsafe_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            with self.assertRaises(ValueError):
                memory_path(root, "memory://session/A B/short")
            with self.assertRaises(ValueError):
                memory_path(root, "memory://session/A@evil/short")


class MemoryLifecycleTests(unittest.TestCase):
    def _write(self, root, uri, content="finding", source=None, **kw):
        write_memory(root, uri, content, source=source or {"session": "s1"}, **kw)

    def test_promote_same_tier_moves_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://task/T17/medium")
            self.assertEqual(
                promote_memory(root, "memory://task/T17/medium")["status"], "active"
            )
            self.assertEqual(
                promote_memory(root, "memory://task/T17/medium")["status"], "verified"
            )
            with self.assertRaises(ValueError):
                promote_memory(root, "memory://task/T17/medium")

    def test_promote_cross_tier_migrates_scope_session_to_task(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short", source={"task": "T17"})
            result = promote_memory(root, "memory://session/A/short", to_tier="medium")
            self.assertEqual(result["status"], "active")
            self.assertEqual(result["uri"], "memory://task/T17/medium")
            self.assertTrue((root / ".agent/memory/medium/task-T17.md").exists())
            self.assertFalse((root / ".agent/memory/short/session-A.md").exists())

    def test_promote_cross_tier_task_to_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://task/T17/medium", source={"project": "ASR"})
            promote_memory(root, "memory://task/T17/medium")
            result = promote_memory(root, "memory://task/T17/medium", to_tier="long")
            self.assertEqual(result["status"], "verified")
            self.assertTrue((root / ".agent/memory/long/project-ASR.md").exists())

    def test_promote_cross_tier_requires_scope_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short", source={})
            with self.assertRaises(ValueError):
                promote_memory(root, "memory://session/A/short", to_tier="medium")

    def test_archive_and_discard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short")
            self.assertEqual(
                archive_memory(root, "memory://session/A/short")["status"], "archived"
            )
            self.assertEqual(
                discard_memory(root, "memory://session/A/short")["status"], "deprecated"
            )

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

    def test_lifecycle_records_audit_events(self):
        from xiaot_memory.observer import list_events

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short", source={"task": "T17"})
            promote_memory(root, "memory://session/A/short", to_tier="medium")
            archive_memory(root, "memory://task/T17/medium")
            events = [e["event"] for e in list_events(root)]
            self.assertIn("memory.promoted", events)
            self.assertIn("memory.archived", events)

    def test_archive_single_entry_by_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short", content="first")
            self._write(root, "memory://session/A/short", content="second")
            result = archive_memory(root, "memory://session/A/short", index=-1)
            self.assertEqual(result["content"], "second")
            self.assertEqual(result["status"], "archived")
            entries = read_memory(root, "memory://session/A/short")
            self.assertEqual(entries[0]["status"], "candidate")
            self.assertEqual(entries[1]["status"], "archived")

    def test_discard_single_entry_by_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short", content="first")
            self._write(root, "memory://session/A/short", content="second")
            result = discard_memory(root, "memory://session/A/short", index=0)
            self.assertEqual(result["content"], "first")
            self.assertEqual(result["status"], "deprecated")
            entries = read_memory(root, "memory://session/A/short")
            self.assertEqual(entries[0]["status"], "deprecated")
            self.assertEqual(entries[1]["status"], "candidate")

    def test_archive_all_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short", content="first")
            self._write(root, "memory://session/A/short", content="second")
            archive_memory(root, "memory://session/A/short", all_=True)
            for entry in read_memory(root, "memory://session/A/short"):
                self.assertEqual(entry["status"], "archived")

    def test_promote_single_entry_cross_tier_keeps_others(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://task/T17/medium", content="first",
                        source={"project": "ASR"})
            self._write(root, "memory://task/T17/medium", content="second",
                        source={"project": "ASR"})
            result = promote_memory(root, "memory://task/T17/medium",
                                    to_tier="long", index=-1)
            self.assertEqual(result["content"], "second")
            self.assertEqual(result["uri"], "memory://project/ASR/long")
            remaining = read_memory(root, "memory://task/T17/medium")
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0]["content"], "first")
            promoted = read_memory(root, "memory://project/ASR/long")
            self.assertEqual(len(promoted), 1)
            self.assertEqual(promoted[0]["content"], "second")

    def test_promote_all_entries_cross_tier_moves_everything(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://task/T17/medium", content="first",
                        source={"project": "ASR"})
            self._write(root, "memory://task/T17/medium", content="second",
                        source={"project": "ASR"})
            promote_memory(root, "memory://task/T17/medium", to_tier="long", all_=True)
            self.assertEqual(len(read_memory(root, "memory://task/T17/medium")), 0)
            promoted = read_memory(root, "memory://project/ASR/long")
            self.assertEqual([e["content"] for e in promoted], ["first", "second"])

    def test_index_out_of_range_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short")
            with self.assertRaises(ValueError):
                archive_memory(root, "memory://session/A/short", index=5)

    def test_promote_all_same_tier_handles_mixed_status_individually(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short", content="c1", status="candidate")
            self._write(root, "memory://session/A/short", content="a1", status="active")
            promote_memory(root, "memory://session/A/short", all_=True)
            statuses = [e["status"] for e in read_memory(root, "memory://session/A/short")]
            self.assertEqual(statuses, ["active", "verified"])

    def test_promote_all_same_tier_aborts_when_any_entry_not_promotable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short", content="c1", status="candidate")
            self._write(root, "memory://session/A/short", content="x1", status="archived")
            with self.assertRaises(ValueError):
                promote_memory(root, "memory://session/A/short", all_=True)
            statuses = [e["status"] for e in read_memory(root, "memory://session/A/short")]
            self.assertEqual(statuses, ["candidate", "archived"])

    def test_promote_same_uri_target_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://project/ASR/long", content="fact",
                        source={"project": "ASR"})
            with self.assertRaises(ValueError):
                promote_memory(root, "memory://project/ASR/long", to_tier="long")
            self.assertEqual(len(read_memory(root, "memory://project/ASR/long")), 1)

    def test_promote_event_records_new_status(self):
        from xiaot_memory.observer import list_events

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short")
            promote_memory(root, "memory://session/A/short")
            events = [e for e in list_events(root) if e["event"] == "memory.promoted"]
            self.assertEqual(events[-1]["data"]["status"], "active")

    def test_promote_all_cross_tier_uses_latest_source_for_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://task/T17/medium", content="first",
                        source={"project": "ASR"})
            self._write(root, "memory://task/T17/medium", content="second",
                        source={"project": "ASR"})
            promote_memory(root, "memory://task/T17/medium", to_tier="long", all_=True)
            promoted = read_memory(root, "memory://project/ASR/long")
            self.assertEqual([e["uri"] for e in promoted], ["memory://project/ASR/long"] * 2)


class StructuredWriteTests(unittest.TestCase):
    def test_write_structured_three_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            item = write_memory_structured(
                root,
                "memory://session/A/short",
                conclusion="beam < 2 skipped",
                constraints=["keep schema"],
                unresolved=["threshold config?"],
                source={"task": "T17"},
            )
            self.assertEqual(item["content"], "beam < 2 skipped")
            self.assertEqual(item["constraints"], ["keep schema"])
            self.assertEqual(item["unresolved"], ["threshold config?"])
            self.assertEqual(item["status"], "candidate")
            loaded = read_memory(root, "memory://session/A/short")[0]
            self.assertEqual(loaded["constraints"], ["keep schema"])
            self.assertEqual(loaded["source"], {"task": "T17"})

    def test_write_structured_partial_fields_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            item = write_memory_structured(
                root, "memory://session/A/short", conclusion="only conclusion",
                source={"task": "T17"},
            )
            self.assertEqual(item["constraints"], [])
            self.assertEqual(item["unresolved"], [])

    def test_write_structured_all_empty_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            with self.assertRaises(ValueError):
                write_memory_structured(root, "memory://session/A/short")

    def test_get_returns_structured_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(
                root,
                "memory://task/T17/medium",
                conclusion="root cause",
                constraints=["keep schema"],
            )
            loaded = read_memory(root, "memory://task/T17/medium")
            self.assertEqual(loaded[0]["content"], "root cause")
            self.assertEqual(loaded[0]["constraints"], ["keep schema"])

    def test_write_records_audit_event(self):
        from xiaot_memory.observer import list_events

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://session/A/short", conclusion="note",
                                    source={"task": "T17"})
            events = [e["event"] for e in list_events(root)]
            self.assertIn("memory.write", events)

    def test_write_session_requires_task_ownership(self):
        # issue-1：session 记忆无 --task 归属时写入必须失败，并提示修复命令
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            with self.assertRaises(ValueError) as ctx:
                write_memory_structured(
                    root, "memory://session/A/short", conclusion="orphan session"
                )
            self.assertIn("--task", str(ctx.exception))
            # task scope 不受该限制
            write_memory_structured(
                root, "memory://task/T17/medium", conclusion="ok without task",
                source={"project": "P"},
            )
            # 合法归属链：带 task 写入 -> 提升到 medium
            write_memory_structured(
                root, "memory://session/A/short", conclusion="with task",
                source={"task": "T17"},
            )
            promoted = promote_memory(
                root, "memory://session/A/short", to_tier="medium"
            )
            self.assertEqual(promoted["uri"], "memory://task/T17/medium")

    def test_repo_relocation_keeps_memory_readable(self):
        # issue-19：仓库整体移动后，AT 相对结构（root/.agent）仍可读写
        with tempfile.TemporaryDirectory() as base:
            root = Path(base) / "repo-v1"
            root.mkdir()
            initialize_workspace(root)
            write_memory_structured(
                root, "memory://task/T17/medium", conclusion="before move",
                source={"project": "P"},
            )
            # 模拟仓库移动：v1 -> v2
            moved = Path(base) / "repo-v2"
            root.rename(moved)
            entries = read_memory(moved, "memory://task/T17/medium")
            self.assertEqual(entries[0]["content"], "before move")
            # 移动后仍可写
            write_memory_structured(
                moved, "memory://task/T18/medium", conclusion="after move",
                source={"project": "P"},
            )
            self.assertEqual(len(read_memory(moved, "memory://task/T18/medium")), 1)


class TestGovernanceOps(unittest.TestCase):
    """场景 14/15：机械操作记录事件；旧数据可读、水合不损坏、机械操作可用。"""

    def _write(self, root, uri, content="finding", source=None, **kw):
        write_memory(root, uri, content, source=source or {"session": "s1"}, **kw)

    def test_governance_ops_record_events(self):
        # 场景 14：verify/supersede/conflict 全部记入审计事件，且每种只记一次（无重复）。
        from xiaot_memory.memory_policy import (
            request_conflict,
            request_supersede,
            request_verify,
        )
        from xiaot_memory.observer import list_events

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://task/T17/medium")
            self._write(root, "memory://task/T18/medium")
            uri = "memory://task/T17/medium"
            request_verify(root, uri, evidence=["test:ok"])
            request_supersede(
                root, uri, replaces_uri="memory://task/T18/medium", confirmed=True
            )
            self._write(root, "memory://session/A/short")
            request_conflict(root, "memory://session/A/short", confirmed=True)
            events = [e["event"] for e in list_events(root)]
            for name in ("memory.verify", "memory.supersede", "memory.conflict"):
                self.assertIn(name, events)
            self.assertEqual(events.count("memory.verify"), 1)
            self.assertEqual(events.count("memory.supersede"), 1)
            self.assertEqual(events.count("memory.conflict"), 1)

    def test_legacy_entry_hydrates_without_mutating(self):
        # 场景 15：旧数据水合补默认值，原 dict 一字不改。
        from xiaot_memory.memory_models import hydrate_entry, is_legacy

        legacy = {
            "content": "old",
            "status": "archived",
            "created_at": "2026-08-01T00:00:00+00:00",
        }
        self.assertTrue(is_legacy(legacy))
        hydrated = hydrate_entry(legacy, uri="memory://task/T17/medium")
        self.assertEqual(hydrated["tier"], "medium")
        self.assertEqual(hydrated["validity"], "archived")
        self.assertTrue(hydrated["id"].startswith("mem-"))
        self.assertEqual(hydrated["content"], "old")
        # 原 dict 未被改写
        self.assertNotIn("tier", legacy)
        self.assertNotIn("validity", legacy)

    def test_old_data_readable_and_mechanical_ops_work(self):
        # 场景 15：旧格式文件可直接读；治理层水合补默认值；文件不被读取改写；
        # verify/supersede/conflict 机械操作可作用于旧数据。
        import yaml

        from xiaot_memory.memory import memory_path, read_memory, verify_memory
        from xiaot_memory.memory_models import hydrate_entry, is_legacy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            uri = "memory://task/T17/medium"
            path = memory_path(root, uri)
            path.parent.mkdir(parents=True, exist_ok=True)
            legacy = {
                "uri": uri,
                "content": "legacy fact",
                "status": "candidate",
                "created_at": "2026-08-01T00:00:00+00:00",
                "source": {"task": "T17"},
            }
            path.write_text(
                yaml.safe_dump_all([legacy], allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            # 旧数据可读
            entries = read_memory(root, uri)
            self.assertEqual(entries[0]["content"], "legacy fact")
            self.assertTrue(is_legacy(entries[0]))
            # 水合补默认值，原 dict 不变
            raw = entries[0]
            hydrated = hydrate_entry(raw)
            self.assertEqual(hydrated["tier"], "medium")
            self.assertNotIn("tier", raw)
            # 读取后文件未被改写（仍为旧格式）
            self.assertNotIn("tier:", path.read_text(encoding="utf-8"))
            # 机械操作可作用于旧数据
            verify_memory(root, uri, evidence=["legacy:user-confirmed"])
            self.assertEqual(read_memory(root, uri)[0]["status"], "verified")


if __name__ == "__main__":
    unittest.main()

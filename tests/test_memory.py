from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.memory import (
    archive_memory,
    discard_memory,
    list_tier_entries,
    memory_path,
    promote_memory,
    read_memory,
    write_memory,
    write_memory_structured,
)
from at_runtime.workspace import initialize_workspace


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
        from at_runtime.observer import list_events

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            self._write(root, "memory://session/A/short", source={"task": "T17"})
            promote_memory(root, "memory://session/A/short", to_tier="medium")
            archive_memory(root, "memory://task/T17/medium")
            events = [e["event"] for e in list_events(root)]
            self.assertIn("memory.promoted", events)
            self.assertIn("memory.archived", events)


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
                root, "memory://session/A/short", conclusion="only conclusion"
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
        from at_runtime.observer import list_events

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory_structured(root, "memory://session/A/short", conclusion="note")
            events = [e["event"] for e in list_events(root)]
            self.assertIn("memory.write", events)


if __name__ == "__main__":
    unittest.main()

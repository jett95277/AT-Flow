from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.memory import memory_path, write_memory, read_memory
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


if __name__ == "__main__":
    unittest.main()

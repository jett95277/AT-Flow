from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot_memory.memory import read_memory, write_memory
from xiaot_memory.memory_context import (
    build_memory_context,
    filter_entries,
    is_injectable,
    resolve_scope_precedence,
)
from xiaot_memory.memory_models import hydrate_entry, make_entry
from xiaot_memory.workspace import initialize_workspace


class TestGovernanceContext(unittest.TestCase):
    # 场景 5：conflicted 不进上下文
    def test_conflicted_not_injectable(self):
        entry = make_entry("memory://session/A/short", "结论", {"task": "T1"})
        entry["status"] = "conflicted"
        self.assertFalse(is_injectable(entry))
        self.assertEqual(filter_entries([entry]), [])

    # 场景 6：archived / superseded / discarded 不进上下文
    def test_inactive_validity_not_injectable(self):
        for validity in ("superseded", "archived", "discarded"):
            entry = make_entry("memory://session/A/short", "结论", {"task": "T1"})
            entry["validity"] = validity
            self.assertFalse(is_injectable(entry), validity)

    # 场景 4：candidate 不覆盖 verified
    def test_candidate_not_override_verified(self):
        cand = make_entry(
            "memory://task/T1/short", "beam 阈值 2", {"task": "T1"}, status="candidate"
        )
        ver = make_entry(
            "memory://global/x/long", "beam 阈值 2", {}, status="verified"
        )
        kept = resolve_scope_precedence([cand, ver])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["status"], "verified")

    # 作用域优先级 task > global
    def test_scope_priority_task_over_global(self):
        task_e = make_entry(
            "memory://task/T1/short", "约束", {"task": "T1"}, status="active"
        )
        global_e = make_entry("memory://global/x/long", "约束", {}, status="active")
        kept = resolve_scope_precedence([task_e, global_e])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["scope"], "task")

    # build_memory_context：无有效 entry 的 ref 进 filtered
    def test_build_memory_context_filters_empty_ref(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            write_memory(root, "memory://project/P/long", "长期结论", {"project": "P"})
            ctx = build_memory_context(
                root,
                ["memory://project/P/long", "memory://project/Q/long"],
            )
            self.assertEqual(ctx["uris"], ["memory://project/P/long"])
            self.assertEqual(ctx["filtered"], ["memory://project/Q/long"])
            self.assertIn("memory://project/P/long", ctx["entries"])
            self.assertEqual(
                hydrate_entry(ctx["entries"]["memory://project/P/long"][0])["content"],
                "长期结论",
            )


if __name__ == "__main__":
    unittest.main()

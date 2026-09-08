"""v3.1 layering tests: Orchestrator state machine + port injection.

Covers change v31-orchestrator-layering tasks 1.2 / 2.1 / 2.2 / 2.3:
- TaskState machine: run_task planning->ready, settle -> completed/failed,
  derived phase stays consistent with workspace artifacts.
- Boundaries: empty memory / empty skills degrade to base path, spec gate.
- Fake port injection: swapping MemoryService drives the core - the core does
  not depend on the concrete implementation.
- derive_phase unit rules incl. the planning placeholder result.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot import commands, memory_service, orchestrator, workspace  # noqa: E402
from xiaot.models import Task, TaskPhase, TaskState, derive_phase  # noqa: E402
from xiaot.orchestrator import Orchestrator  # noqa: E402


class DerivePhaseTests(unittest.TestCase):
    def test_task_state_alias_same_enum(self):
        # v3.1: TaskState (in-process machine) == TaskPhase (derived view)
        self.assertIs(TaskState, TaskPhase)
        self.assertEqual(TaskState.READY.value, "ready")
    def test_no_plan_is_planning(self):
        self.assertEqual(derive_phase(False, False), TaskPhase.PLANNING)
        self.assertEqual(derive_phase(False, True, "success"), TaskPhase.PLANNING)

    def test_plan_without_result_is_ready(self):
        self.assertEqual(derive_phase(True, False), TaskPhase.READY)

    def test_planning_placeholder_is_ready_not_failed(self):
        # new task writes result.md status=planning as placeholder
        self.assertEqual(derive_phase(True, True, "planning"), TaskPhase.READY)
        self.assertEqual(derive_phase(True, True, None), TaskPhase.READY)

    def test_terminal_statuses(self):
        self.assertEqual(derive_phase(True, True, "success"), TaskPhase.COMPLETED)
        self.assertEqual(derive_phase(True, True, "partial"), TaskPhase.COMPLETED)
        self.assertEqual(derive_phase(True, True, "failed"), TaskPhase.FAILED)
        self.assertEqual(derive_phase(True, True, "cancelled"), TaskPhase.FAILED)


class OrchestratorStateMachineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.orch = orchestrator.assemble_default(root=self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_run_task_lands_ready(self):
        r = self.orch.run_task("继续修模块X", project="P")
        self.assertTrue(r["ok"])
        self.assertEqual(r["phase"], TaskPhase.READY.value)
        self.assertTrue((self.root / ".xiaot" / "workspace" / r["task_id"]
                         / "plan.md").exists())
        self.assertTrue((self.root / ".xiaot" / "workspace" / r["task_id"]
                         / "context.json").exists())
        # derived phase agrees with the returned one
        self.assertEqual(self.orch.phase_of(r["task_id"]).value, r["phase"])

    def test_settle_completed_and_failed(self):
        tid = self.orch.run_task("x", project="P")["task_id"]
        s = self.orch.settle(tid, status="success", output="done")
        self.assertEqual(s["phase"], TaskPhase.COMPLETED.value)
        self.assertEqual(self.orch.phase_of(tid), TaskPhase.COMPLETED)
        self.orch.settle(tid, status="failed", output="boom")
        self.assertEqual(self.orch.phase_of(tid), TaskPhase.FAILED)

    def test_resume_unknown_fails(self):
        r = self.orch.run_task("x", resume="task-nope")
        self.assertFalse(r["ok"])
        self.assertIn("not found", r["error"])

    def test_resume_reads_plan_goal(self):
        r1 = self.orch.run_task("目标甲", project="P")
        tid = r1["task_id"]
        # resume without prompt reuses stored goal -> context instruction has it
        r2 = self.orch.run_task("ignored", resume=tid)
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["task_id"], tid)
        self.assertIn("目标甲", r2["context"]["instruction"])

    def test_resume_invalid_task_id_fails_cleanly(self):
        # task ids are embedded in filesystem paths; traversal must not escape
        # (empty string is falsy -> treated as a new task, not a resume id)
        for bad in ("..", "../x", "a/b", "."):
            r = self.orch.run_task("x", resume=bad)
            self.assertFalse(r["ok"], bad)
            self.assertIn("invalid task id", r["error"], bad)
        # no task workspace was created and nothing escaped the tree:
        # .xiaot itself may exist (project-name probe), but never a workspace
        # dir or a file written outside .xiaot/workspace/<valid-id>/
        self.assertFalse((self.root / ".xiaot" / "workspace").exists())
        self.assertFalse((self.root / "context.json").exists())
        self.assertFalse((self.root / ".xiaot" / "context.json").exists())

    def test_resume_completed_task_stays_completed(self):
        r1 = self.orch.run_task("done task", project="P")
        tid = r1["task_id"]
        self.orch.settle(tid, status="success", output="done")
        self.assertEqual(self.orch.phase_of(tid), TaskPhase.COMPLETED)
        # resuming a completed task reports the derived phase, never ready
        r2 = self.orch.run_task("again", resume=tid)
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["phase"], TaskPhase.COMPLETED.value)
        self.assertEqual(self.orch.phase_of(tid), TaskPhase.COMPLETED)

    def test_workspace_layer_rejects_traversal(self):
        import xiaot.workspace as ws
        for bad in ("..", "../x", "a/b", ".", ""):
            with self.assertRaises(ValueError, msg=bad):
                ws.workspace_dir(self.root, bad)
            with self.assertRaises(ValueError, msg=bad):
                ws.workspace_exists(self.root, bad)
    def test_spec_flagged_task_gets_guidance_not_gate(self):
        # spec decision is advisory: flagged task proceeds and carries
        # guidance; no hard error even when the CLI is unavailable.
        class NoSpec:
            def should_spec(self, prompt):  # noqa: ARG002
                return {"needs_spec": True, "reason": "signal",
                        "scale": "large"}
            def available(self):
                return False

        o = Orchestrator(root=self.root,
                         memory=self.orch._memory,
                         skills=self.orch._skills,
                         spec=NoSpec(),
                         store=self.orch._store,
                         context=self.orch._context)
        r = o.run_task("实现一个很大的新功能模块", project="P")
        self.assertTrue(r["ok"])  # never blocked by missing spec CLI
        self.assertTrue(r["spec"]["needs_spec"])
        self.assertIn("guidance", r["spec"])
        self.assertIn("spec workflow", r["spec"]["guidance"])


class PortInjectionTests(unittest.TestCase):
    """Core must run driven by fake ports - no dependency on real adapters."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.calls: list[str] = []

    def tearDown(self):
        self._tmp.cleanup()

    def test_fake_memory_drives_orchestrator(self):
        class FakeMemory:
            def __init__(self, calls: list[str]):
                self.calls = calls

            def retrieve(self, root, task, budget=5):  # noqa: ARG002
                self.calls.append("retrieve")
                return {"present": True,
                        "summary": [{"uri": "memory://task/fake/medium",
                                     "summary": "fake memory"}],
                        "refs": {"total": 1, "inline": 1, "uris": []}}

            def suggest_settle(self, root, task_id, candidates=None):  # noqa: ARG002
                self.calls.append("suggest_settle")
                return {"suggestions": [{"action": "review",
                                         "text": "fake settle"}],
                        "policy": "all_promotions_manual"}

        class FakeSkills:
            def resolve(self, prompt, limit=3):  # noqa: ARG002
                return [{"name": "fake-skill", "matched": ["fake"]}]

        class FakeSpec:
            def should_spec(self, prompt):  # noqa: ARG002
                return {"needs_spec": False, "reason": "none"}
            def available(self):
                return True

        class FakeContext:
            def build(self, task: Task, memory, skill_hints=None,
                      spec_decision=None):
                return {"task_id": task.id,
                        "instruction": f"Execute: {task.prompt}",
                        "memory_present": bool(memory.get("present")),
                        "memory_summary": memory.get("summary", []),
                        "memory_refs": memory.get("refs", {}),
                        "skill_hints": skill_hints or [],
                        "spec_decision": spec_decision or {},
                        "constraints": []}

        fake_mem = FakeMemory(self.calls)
        orch = Orchestrator(root=self.root, memory=fake_mem,
                            skills=FakeSkills(), spec=FakeSpec(),
                            store=workspace, context=FakeContext())
        r = orch.run_task("fake-driven task", project="FP")
        self.assertTrue(r["ok"])
        self.assertIn("retrieve", self.calls)
        self.assertEqual(r["memory"]["summary"][0]["summary"], "fake memory")
        self.assertEqual(r["skills"][0]["name"], "fake-skill")
        self.assertEqual(r["context"]["instruction"], "Execute: fake-driven task")
        # settle through the same fake memory
        s = orch.settle(r["task_id"], status="success", output="ok")
        self.assertIn("suggest_settle", self.calls)
        self.assertEqual(s["suggestions"][0]["action"], "review")

    def test_unassembled_orchestrator_raises_clear_error(self):
        orch = Orchestrator(root=self.root)  # no ports injected
        with self.assertRaises(RuntimeError) as cm:
            orch.run_task("x")
        self.assertIn("not assembled", str(cm.exception))


class ProjectNamePinningTests(unittest.TestCase):
    """xiaot init pins the canonical project name; --project defaults to it.

    Fixes cross-session memory drift: sessions omitting --project share the
    pinned name, explicit --project still wins.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self._tmp.name) / "my-app"
        self.proj.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_init_pins_dirname(self):
        r = commands.init(project_root=self.proj)
        self.assertTrue(r["ok"])
        self.assertEqual(r["project_name"], "my-app")
        self.assertEqual(workspace.read_project_name(self.proj), "my-app")

    def test_init_explicit_project_wins(self):
        r = commands.init(project_root=self.proj, project_name="canon")
        self.assertEqual(r["project_name"], "canon")
        self.assertEqual(workspace.read_project_name(self.proj), "canon")

    def test_task_omits_project_uses_pinned(self):
        commands.init(project_root=self.proj)  # pins "my-app"
        t = commands.task("继续 my-app 开发", root=self.proj)  # no --project
        self.assertTrue(t["ok"])
        # memory candidate uris carry the pinned project scope
        uris = t["memory"]["uris"]
        self.assertIn("memory://project/my-app/medium", uris)

    def test_confirm_omits_project_uses_pinned(self):
        commands.init(project_root=self.proj)
        c = commands.confirm("项目级结论：用 xx", scope="project",
                             root=self.proj)  # no --project
        self.assertTrue(c["ok"], c)
        self.assertEqual(c["uri"], "memory://project/my-app/medium")

    def test_explicit_project_still_wins(self):
        commands.init(project_root=self.proj)  # pinned "my-app"
        t = commands.task("x", project="other", root=self.proj)
        self.assertIn("memory://project/other/medium", t["memory"]["uris"])
        self.assertNotIn("memory://project/my-app/medium", t["memory"]["uris"])


class CommandsThinRegressionTests(unittest.TestCase):
    """Commands.task/settle stay thin over the Orchestrator (v3.1 thinning)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_task_still_returns_legacy_surface(self):
        r = commands.task("重构记忆模块", project="demo", root=self.root)
        self.assertTrue(r["ok"])
        for key in ("ok", "command", "task_id", "workspace", "memory",
                    "skills", "spec", "context", "state"):
            self.assertIn(key, r)
        self.assertIn("memory_summary", r["context"])
        self.assertEqual(r["command"], "task")

    def test_settle_still_returns_legacy_surface(self):
        t = commands.task("do thing", project="P", root=self.root)
        s = commands.settle(t["task_id"], status="success", output="done",
                            root=self.root)
        self.assertEqual(s["status"], "success")
        self.assertEqual(s["policy"], "all_promotions_manual")


class AuditFixRegressionTests(unittest.TestCase):
    """Regressions for full-review findings (A1-A4, C5): traversal guards on
    timeline node ids, settle workspace existence, confirm topic round-trip,
    CLI JSON error envelope."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_timeline_rollback_rejects_traversal_node_id(self):
        from xiaot import timeline
        for bad in ("..", "../evil", "a/b", ".", ""):
            r = timeline.rollback(self.root, bad)
            self.assertFalse(r["ok"], bad)
            self.assertIn("invalid timeline node id", r["error"], bad)
        # nothing outside timeline tree was touched
        self.assertFalse((self.root / ".xiaot" / "evil").exists())

    def test_settle_unknown_workspace_fails(self):
        orch = orchestrator.assemble_default(root=self.root)
        r = orch.settle("task-00000000", status="success", output="x")
        self.assertFalse(r["ok"])
        self.assertIn("not found", r["error"])
        # no ghost workspace/result created
        self.assertFalse((self.root / ".xiaot" / "workspace"
                          / "task-00000000").exists())

    def test_confirm_task_topic_round_trips(self):
        # full task id from run_task -> confirm writes under the bare topic ->
        # a later retrieve on the same task id injects it back
        from xiaot_memory.memory import read_memory
        orch = orchestrator.assemble_default(root=self.root)
        t = orch.run_task("topic-alpha 结论", project="P")
        tid = t["task_id"]  # task-<hex>
        c = orch.confirm("topic-alpha 已定稿", scope="task", task_id=tid)
        self.assertTrue(c["ok"], c)
        self.assertEqual(c["uri"], f"memory://task/{tid[5:]}/medium")
        # file exists under task-<topic>.md (not task-task-<topic>.md)
        files = [p.name for p in (self.root / ".agent" / "memory" / "medium"
                                  ).glob("task-*.md")]
        self.assertIn(f"task-{tid[5:]}.md", files)
        self.assertNotIn(f"task-{tid}.md", files)
        r = memory_service.retrieve(self.root,
                                    {"id": tid, "project": "P"}, budget=5)
        self.assertTrue(r["present"])
        self.assertIn("topic-alpha 已定稿",
                      " ".join(s["summary"] for s in r["summary"]))


if __name__ == "__main__":
    unittest.main()

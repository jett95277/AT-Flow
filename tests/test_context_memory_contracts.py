from pathlib import Path
import json
import os
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.engine import Runner
from at_flow.models import SessionState
from at_flow.trace import read_trace_events
from at_flow.workspace import ATWorkspace


class ContextMemoryContractTests(unittest.TestCase):
    def test_workspace_initializes_memory_and_policy_contract_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            for name in ("user.md", "project.md", "decisions.md", "rules.md"):
                self.assertTrue((workspace.shared_root / "memory" / name).exists())
            for name in ("context.md", "memory.md"):
                self.assertTrue((workspace.shared_root / "policies" / name).exists())

    def test_runner_writes_agent_context_contract_before_provider_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            script = _write_provider(
                Path(directory),
                "read_context.py",
                """
                from pathlib import Path
                import json
                import os

                for forbidden in ("AT_WORKSPACE_ROOT", "AT_SHARED_ROOT", "AT_SESSION_DIR"):
                    if forbidden in os.environ:
                        raise SystemExit(f"leaked {forbidden}")

                context_path = Path(os.environ["AT_CONTEXT"])
                context = json.loads(context_path.read_text(encoding="utf-8"))

                if "workspace_root" in context or "shared_root" in context or "session_dir" in context:
                    raise SystemExit("context contract leaked a root path")
                if context["agent"] != "main":
                    raise SystemExit("wrong agent context")
                if context["paths"]["project"] is not None:
                    raise SystemExit("main must not receive a project path in context")
                if context["paths"]["shared"]["memory"] is not None:
                    raise SystemExit("main must not receive shared memory directory")
                if not context["selected_files"]["shared_memory"]:
                    raise SystemExit("main should receive authorized shared memory files")

                Path(os.environ["AT_OUTBOX"], "artifact.md").write_text(
                    "# main artifact\\n\\n"
                    "## Task Summary\\n\\nContext contract checked.\\n\\n"
                    "## Goal\\n\\nVerify context boundaries.\\n\\n"
                    "## Non-Goals\\n\\nNo implementation work.\\n\\n"
                    "## Constraints\\n\\nUse AT_CONTEXT only.\\n\\n"
                    "## Acceptance Criteria\\n\\nNo root paths leak.\\n\\n"
                    "## Risks And Questions\\n\\nNone.\\n\\n"
                    "## Handoff To Analysis\\n\\nContext is ready.\\n",
                    encoding="utf-8",
                )
                """,
            )
            workspace.config["providers"]["context-reader"] = _provider(script)
            session = SessionState.new(
                task="context contract",
                project_path=workspace.projects_root / "demo",
                provider="context-reader",
                pipeline=["main"],
            )
            workspace.create_session(session)

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.is_complete())
            session_context = workspace.session_dir(session.id) / "context" / "main.json"
            self.assertTrue(session_context.exists())
            prompt = (workspace.session_agent_dir(session.id, "main") / "prompt.md").read_text(encoding="utf-8")
            self.assertIn("Context Contract (`context.json`):", prompt)
            self.assertNotIn("Shared root:", prompt)
            self.assertNotIn("Workspace root:", prompt)
            self.assertNotIn("Session root:", prompt)

    def test_context_contract_lists_authorized_shared_files_without_shared_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            (workspace.shared_root / "skills" / "review.md").write_text("review skill", encoding="utf-8")
            script = _write_provider(
                Path(directory),
                "read_selected_files.py",
                """
                from pathlib import Path
                import json
                import os

                if os.environ["AT_SHARED_MEMORY"]:
                    raise SystemExit("shared memory directory leaked through env")
                if os.environ["AT_SHARED_SKILLS"]:
                    raise SystemExit("shared skills directory leaked through env")
                if os.environ["AT_SHARED_INBOX"]:
                    raise SystemExit("shared inbox directory leaked through env")

                context = json.loads(Path(os.environ["AT_CONTEXT"]).read_text(encoding="utf-8"))
                if context["paths"]["shared"]["memory"] is not None:
                    raise SystemExit("shared memory directory leaked through context")
                if context["paths"]["shared"]["skills"] is not None:
                    raise SystemExit("shared skills directory leaked through context")

                selected = context["selected_files"]
                memory_names = [Path(path).name for path in selected["shared_memory"]]
                skill_names = [Path(path).name for path in selected["shared_skills"]]
                if "user.md" not in memory_names:
                    raise SystemExit("authorized memory file missing")
                if "review.md" not in skill_names:
                    raise SystemExit("authorized skill file missing")

                Path(os.environ["AT_OUTBOX"], "artifact.md").write_text(
                    "# main artifact\\n\\n"
                    "## Task Summary\\n\\nSelected files checked.\\n\\n"
                    "## Goal\\n\\nVerify file-level shared authorization.\\n\\n"
                    "## Non-Goals\\n\\nNo directory access.\\n\\n"
                    "## Constraints\\n\\nUse selected_files.\\n\\n"
                    "## Acceptance Criteria\\n\\nAuthorized files are listed.\\n\\n"
                    "## Risks And Questions\\n\\nNone.\\n\\n"
                    "## Handoff To Analysis\\n\\nSelected files are available.\\n",
                    encoding="utf-8",
                )
                """,
            )
            workspace.config["providers"]["selected-files"] = _provider(script)
            session = SessionState.new(
                task="selected shared files",
                project_path=workspace.projects_root / "demo",
                provider="selected-files",
                pipeline=["main"],
            )
            workspace.create_session(session)

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.is_complete())
            selected = json.loads((workspace.session_dir(session.id) / "context" / "main.json").read_text(encoding="utf-8"))["selected_files"]
            self.assertTrue(any(path.endswith("user.md") for path in selected["shared_memory"]))
            self.assertTrue(any(path.endswith("review.md") for path in selected["shared_skills"]))

    def test_memory_proposals_are_collected_without_mutating_shared_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            script = _write_provider(
                Path(directory),
                "memory_proposal.py",
                """
                from pathlib import Path
                import os

                proposals = Path(os.environ["AT_OUTBOX"], "proposals")
                proposals.mkdir(parents=True, exist_ok=True)
                (proposals / "memory.md").write_text("remember this", encoding="utf-8")
                Path(os.environ["AT_OUTBOX"], "artifact.md").write_text(
                    "# code artifact\\n\\n"
                    "## Changed Files\\n\\nNone.\\n\\n"
                    "## Behavioral Changes\\n\\nCreated memory proposal.\\n\\n"
                    "## Assumptions\\n\\nProposal collection is enabled.\\n\\n"
                    "## Commands Run\\n\\nNone.\\n\\n"
                    "## Risks Left For Test\\n\\nNone.\\n\\n"
                    "## Verification Suggestions\\n\\nCheck memory-proposals.\\n",
                    encoding="utf-8"
                )
                """,
            )
            workspace.config["providers"]["memory-proposal"] = _provider(script)
            session = SessionState.new(
                task="memory proposal",
                project_path=workspace.projects_root / "demo",
                provider="memory-proposal",
                pipeline=["code"],
            )
            workspace.create_session(session)

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.is_complete())
            collected = workspace.session_dir(session.id) / "memory-proposals" / "code-memory.md"
            self.assertEqual(collected.read_text(encoding="utf-8"), "remember this")
            self.assertFalse((workspace.shared_root / "memory" / "memory.md").exists())

            events = read_trace_events(workspace.session_dir(session.id) / "trace.jsonl")
            self.assertIn("collect_memory_proposals", [event["event"] for event in events])


def _provider(script: Path) -> dict[str, object]:
    return {
        "type": "process",
        "command": [sys.executable, str(script)],
        "prompt_mode": "stdin",
        "cwd": "workspace",
        "env_policy": "minimal",
        "timeout_seconds": 30,
    }


def _write_provider(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()

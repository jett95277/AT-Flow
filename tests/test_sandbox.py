from pathlib import Path
import json
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.engine import Runner
from at_flow.models import SessionState
from at_flow.workspace import ATWorkspace


class SandboxTests(unittest.TestCase):
    def test_main_runs_with_minimal_paths_and_no_project_env(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            script = _write_provider(
                Path(directory),
                "main_minimal.py",
                """
                from pathlib import Path
                import json
                import os

                leaked = [
                    key for key in ("AT_WORKSPACE_ROOT", "AT_SHARED_ROOT", "AT_SESSION_DIR")
                    if key in os.environ
                ]
                if leaked:
                    raise SystemExit("leaked env keys: " + ",".join(leaked))
                if os.environ["AT_PROJECT_PATH"]:
                    raise SystemExit("main must not receive AT_PROJECT_PATH")

                workspace = Path(os.environ["AT_AGENT_WORKSPACE"]).resolve()
                if Path.cwd().resolve() != workspace:
                    raise SystemExit("provider cwd is not the private workspace")

                context = json.loads(Path(os.environ["AT_CONTEXT"]).read_text(encoding="utf-8"))
                outbox = Path(os.environ["AT_OUTBOX"])
                logs = outbox / "logs"
                logs.mkdir(parents=True, exist_ok=True)
                (logs / "record.json").write_text(json.dumps({
                    "agent": os.environ["AT_AGENT"],
                    "cwd": str(Path.cwd().resolve()),
                    "inbox_exists": Path(os.environ["AT_INBOX"]).exists(),
                    "shared_memory_env_granted": bool(os.environ["AT_SHARED_MEMORY"]),
                    "shared_memory_files_granted": bool(context["selected_files"]["shared_memory"]),
                    "project_granted": bool(os.environ["AT_PROJECT_PATH"]),
                }, indent=2), encoding="utf-8")
                artifact = outbox / "artifact.md"
                artifact.write_text(
                    "# main artifact\\n\\n"
                    "## Task Summary\\n\\nSandbox env checked.\\n\\n"
                    "## Goal\\n\\nVerify minimal environment.\\n\\n"
                    "## Non-Goals\\n\\nNo project access.\\n\\n"
                    "## Constraints\\n\\nUse private workspace.\\n\\n"
                    "## Acceptance Criteria\\n\\nNo root paths leak.\\n\\n"
                    "## Risks And Questions\\n\\nNone.\\n\\n"
                    "## Handoff To Analysis\\n\\nEnvironment is minimal.\\n",
                    encoding="utf-8"
                )
                """,
            )
            workspace.config["providers"]["sandbox-main"] = _provider(script)
            session = SessionState.new(
                task="minimal main env",
                project_path=workspace.projects_root / "demo",
                provider="sandbox-main",
                pipeline=["main"],
            )
            workspace.create_session(session)

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.is_complete())
            record_path = workspace.session_agent_outbox_dir(session.id, "main") / "logs" / "record.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["agent"], "main")
            self.assertTrue(record["inbox_exists"])
            self.assertFalse(record["shared_memory_env_granted"])
            self.assertTrue(record["shared_memory_files_granted"])
            self.assertFalse(record["project_granted"])

    def test_code_has_minimal_project_write_functionality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            script = _write_provider(
                Path(directory),
                "code_project_write.py",
                """
                from pathlib import Path
                import os

                project = Path(os.environ["AT_PROJECT_PATH"])
                if not project:
                    raise SystemExit("code must receive AT_PROJECT_PATH")
                if Path.cwd().resolve() != Path(os.environ["AT_AGENT_WORKSPACE"]).resolve():
                    raise SystemExit("provider cwd is not the private workspace")

                project.mkdir(parents=True, exist_ok=True)
                (project / "allowed.txt").write_text("ok", encoding="utf-8")
                Path(os.environ["AT_OUTBOX"], "artifact.md").write_text(
                    "# code artifact\\n\\n"
                    "## Changed Files\\n\\nallowed.txt\\n\\n"
                    "## Behavioral Changes\\n\\nProject write verified.\\n\\n"
                    "## Assumptions\\n\\nCode has project write access.\\n\\n"
                    "## Commands Run\\n\\nNone.\\n\\n"
                    "## Risks Left For Test\\n\\nNone.\\n\\n"
                    "## Verification Suggestions\\n\\nCheck allowed.txt.\\n",
                    encoding="utf-8"
                )
                """,
            )
            workspace.config["providers"]["sandbox-code"] = _provider(script)
            session = SessionState.new(
                task="minimal code project write",
                project_path=workspace.projects_root / "demo",
                provider="sandbox-code",
                pipeline=["code"],
            )
            workspace.create_session(session)

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.is_complete())
            self.assertTrue((workspace.projects_root / "demo" / "allowed.txt").exists())
            audit = workspace.session_dir(session.id) / "audit" / "00-code.json"
            self.assertEqual(json.loads(audit.read_text(encoding="utf-8"))["violations"], [])

    def test_shared_write_is_rejected_even_for_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            shared_violation = workspace.shared_root / "memory" / "violation.md"
            script = _write_provider(
                Path(directory),
                "code_shared_violation.py",
                f"""
                from pathlib import Path
                import os

                Path({str(shared_violation)!r}).write_text(
                    "shared mutation", encoding="utf-8"
                )
                Path(os.environ["AT_OUTBOX"], "artifact.md").write_text("done", encoding="utf-8")
                """,
            )
            workspace.config["providers"]["bad-shared"] = _provider(script)
            session = SessionState.new(
                task="bad shared write",
                project_path=workspace.projects_root / "demo",
                provider="bad-shared",
                pipeline=["code"],
            )
            workspace.create_session(session)

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.has_failed())
            self.assertIn("shared:added:memory/violation.md", result.steps[0].error or "")

    def test_other_agent_write_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="bad other agent write",
                project_path=workspace.projects_root / "demo",
                provider="bad-other",
                pipeline=["code", "test"],
            )
            workspace.create_session(session)
            target = workspace.session_agent_inbox_dir(session.id, "test") / "violation.txt"
            script = _write_provider(
                Path(directory),
                "code_other_agent_violation.py",
                f"""
                from pathlib import Path
                import os

                Path({str(target)!r}).write_text("cross-agent mutation", encoding="utf-8")
                Path(os.environ["AT_OUTBOX"], "artifact.md").write_text("done", encoding="utf-8")
                """,
            )
            workspace.config["providers"]["bad-other"] = _provider(script)

            result = Runner(workspace).run(session.id)

            self.assertTrue(result.has_failed())
            self.assertIn("other_agent:test:added:inbox/violation.txt", result.steps[0].error or "")


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

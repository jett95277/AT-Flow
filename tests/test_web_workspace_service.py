from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.web.errors import ApiError
from at_flow.web.workspace_service import WorkspaceService
from at_flow.workspace import ATWorkspace


def flatten(nodes):
    result = []
    for node in nodes:
        result.append(node)
        result.extend(flatten(node.children))
    return result


class WorkspaceServiceTests(unittest.TestCase):
    def test_workspace_tree_exposes_agent_documents_without_duplicate_shared_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            tree = WorkspaceService(workspace).tree()

            paths = {node.path for node in flatten(tree)}
            self.assertIn("agents/main/agent.md", paths)
            self.assertIn("shared/memory/user.md", paths)
            self.assertNotIn("shared/agents/main/agent.md", paths)

    def test_workspace_tree_keeps_unrelated_shared_agents_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            shared_agents = workspace.shared_root / "agents"
            shared_agents.mkdir()
            (shared_agents / "notes.md").write_text("shared notes", encoding="utf-8")

            paths = {node.path for node in flatten(WorkspaceService(workspace).tree())}

            self.assertIn("shared/agents/notes.md", paths)

    def test_workspace_tree_hides_translation_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            display = workspace.agents_root / "main" / "agent.zh.md"
            display.write_text("中文副本", encoding="utf-8")

            paths = {node.path for node in flatten(WorkspaceService(workspace).tree())}

            self.assertIn("agents/main/agent.md", paths)
            self.assertNotIn("agents/main/agent.zh.md", paths)

    def test_read_file_allows_tree_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            text = WorkspaceService(workspace).read_file("agents/main/agent.md")

            self.assertIn("main", text.lower())

    def test_read_file_prefers_chinese_display_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            source = workspace.agents_root / "main" / "agent.md"
            source.write_text("English contract content", encoding="utf-8")
            source.with_name("agent.zh.md").write_text("中文契约内容", encoding="utf-8")
            service = WorkspaceService(workspace)

            zh_text = service.read_file("agents/main/agent.md")
            en_text = service.read_file("agents/main/agent.md", language="en")

            self.assertIn("中文契约内容", zh_text)
            self.assertIn("English contract content", en_text)

    def test_read_file_returns_source_when_no_display_copy_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            service = WorkspaceService(workspace)

            text = service.read_file("agents/main/agent.md")

            self.assertIn("main", text.lower())
            self.assertNotIn("agent.zh.md", text)

    def test_read_file_translates_session_document_on_demand(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            workspace.config["language"].update(
                {
                    "enabled": True,
                    "source": "zh",
                    "runtime": "en",
                    "display": "zh",
                    "translation_provider": "test-translator",
                }
            )
            session_dir = workspace.session_dir("s1")
            prompt_dir = session_dir / "agents" / "main"
            prompt_dir.mkdir(parents=True)
            source = prompt_dir / "prompt.md"
            source.write_text("Implement the login module", encoding="utf-8")
            calls = []

            class FakeTranslator:
                name = "test-translator"

                def translate(self, text, source_language, target_language, purpose):
                    calls.append((text, source_language, target_language, purpose))
                    return "实现登录模块"

            service = WorkspaceService(
                workspace, translator_factory=lambda config, name, work_dir: FakeTranslator()
            )

            zh_text = service.read_file("sessions/s1/agents/main/prompt.md")

            self.assertEqual(zh_text, "实现登录模块\n")
            self.assertEqual(calls[0][1:], ("en", "zh", "document"))
            self.assertTrue((prompt_dir / "prompt.zh.md").is_file())

            second = service.read_file("sessions/s1/agents/main/prompt.md")
            self.assertEqual(second, "实现登录模块\n")
            self.assertEqual(len(calls), 1)

    def test_read_file_session_translation_failure_raises_typed_error(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            workspace.config["language"].update(
                {
                    "enabled": True,
                    "source": "zh",
                    "runtime": "en",
                    "display": "zh",
                    "translation_provider": "test-translator",
                }
            )
            session_dir = workspace.session_dir("s1")
            prompt_dir = session_dir / "agents" / "main"
            prompt_dir.mkdir(parents=True)
            (prompt_dir / "prompt.md").write_text("Implement the login module", encoding="utf-8")

            class FailingTranslator:
                name = "test-translator"

                def translate(self, text, source_language, target_language, purpose):
                    from at_flow.language.translator import TranslationError

                    raise TranslationError("translation_process_failed", "offline", retryable=True)

            service = WorkspaceService(
                workspace, translator_factory=lambda config, name, work_dir: FailingTranslator()
            )

            with self.assertRaises(ApiError) as raised:
                service.read_file("sessions/s1/agents/main/prompt.md")

            self.assertEqual(raised.exception.code, "display_translation_failed")
            self.assertTrue(raised.exception.retryable)
            self.assertFalse((prompt_dir / "prompt.zh.md").exists())

    def test_read_file_session_document_language_en_returns_source(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session_dir = workspace.session_dir("s1")
            prompt_dir = session_dir / "agents" / "main"
            prompt_dir.mkdir(parents=True)
            source = prompt_dir / "prompt.md"
            source.write_text("Implement the login module", encoding="utf-8")

            service = WorkspaceService(workspace)

            text = service.read_file("sessions/s1/agents/main/prompt.md", language="en")

            self.assertIn("Implement the login module", text)
            self.assertFalse((prompt_dir / "prompt.zh.md").exists())

    def test_workspace_tree_hides_session_translation_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            prompt_dir = workspace.session_dir("s1") / "agents" / "main"
            prompt_dir.mkdir(parents=True)
            (prompt_dir / "prompt.md").write_text("Implement the login module", encoding="utf-8")
            (prompt_dir / "prompt.zh.md").write_text("实现登录模块", encoding="utf-8")

            paths = {node.path for node in flatten(WorkspaceService(workspace).tree())}

            self.assertIn("sessions/s1/agents/main/prompt.md", paths)
            self.assertNotIn("sessions/s1/agents/main/prompt.zh.md", paths)

    def test_read_file_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            with self.assertRaises(ApiError) as raised:
                WorkspaceService(workspace).read_file("../at.config.json")

            self.assertEqual(raised.exception.code, "file_not_allowed")

    def test_read_file_rejects_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            absolute = str(workspace.root / "at.config.json")

            with self.assertRaises(ApiError) as raised:
                WorkspaceService(workspace).read_file(absolute)

            self.assertEqual(raised.exception.code, "file_not_allowed")

    def test_read_file_rejects_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            with self.assertRaises(ApiError) as raised:
                WorkspaceService(workspace).read_file("agents/main")

            self.assertEqual(raised.exception.code, "file_not_allowed")


if __name__ == "__main__":
    unittest.main()

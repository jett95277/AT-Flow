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

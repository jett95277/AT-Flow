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
    def test_workspace_tree_exposes_agent_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            tree = WorkspaceService(workspace).tree()

            paths = {node.path for node in flatten(tree)}
            self.assertIn("agents/main/agent.md", paths)

    def test_read_file_allows_tree_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            text = WorkspaceService(workspace).read_file("agents/main/agent.md")

            self.assertIn("main", text.lower())

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

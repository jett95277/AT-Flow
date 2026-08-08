from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.workspace import initialize_workspace, load_manifest, load_policies


class WorkspaceTests(unittest.TestCase):
    def test_init_creates_agent_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            for relative in (
                ".agent/manifest.yaml",
                ".agent/policies.yaml",
                ".agent/runtime/sessions",
                ".agent/runtime/tasks",
                ".agent/runtime/events",
                ".agent/contexts/bundles",
                ".agent/memory/short",
                ".agent/memory/medium",
                ".agent/memory/long",
                ".agent/handoffs",
                ".agent/artifacts",
                ".agent/knowledge/refs",
            ):
                self.assertTrue((root / relative).exists(), relative)

    def test_manifest_has_project_and_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            manifest = load_manifest(root)
            self.assertIn("project", manifest)
            self.assertIn("runtime", manifest)

    def test_policies_have_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            policies = load_policies(root)
            self.assertIn("analysis", policies["roles"])
            self.assertIn("code", policies["roles"])
            self.assertIn("test", policies["roles"])


if __name__ == "__main__":
    unittest.main()

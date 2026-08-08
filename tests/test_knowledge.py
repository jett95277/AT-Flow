from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.knowledge import get_knowledge, propose_knowledge, query_knowledge
from at_runtime.workspace import initialize_workspace


class KnowledgeTests(unittest.TestCase):
    def test_propose_and_query(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            propose_knowledge(
                root,
                "voice-quality/scoring",
                "beam < 2 means skipped",
                {"session": "test-T17"},
            )
            hits = query_knowledge(root, "voice-quality")
            self.assertEqual(len(hits), 1)
            ref = hits[0]["ref"]
            self.assertIsNotNone(get_knowledge(root, ref))


if __name__ == "__main__":
    unittest.main()

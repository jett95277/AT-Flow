from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_runtime.observer import list_events, record_event
from at_runtime.workspace import initialize_workspace


class ObserverTests(unittest.TestCase):
    def test_events_are_appended(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            record_event(root, "session.created", "s1", {"role": "analysis"})
            record_event(root, "context.injected", "s1", {"tokens": 1234})
            events = list_events(root)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[1]["event"], "context.injected")
            self.assertEqual(events[1]["data"]["tokens"], 1234)
            self.assertIn("ts", events[0])


if __name__ == "__main__":
    unittest.main()

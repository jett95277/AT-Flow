from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.models import SessionState
from at_flow.render import render_chat_panel, render_chat_session


class RenderTests(unittest.TestCase):
    def test_chat_render_shows_ascii_at_state_before_codex_layer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = SessionState.new(
                task="demo",
                project_path=Path(directory) / "project",
                provider="mock",
            )

            rendered = render_chat_session(session)

            self.assertIn("**AT State Machine**", rendered)
            self.assertIn("+----------+", rendered)
            self.assertIn("| main     | --> | analysis |", rendered)
            self.assertIn("**Current Stage**", rendered)
            self.assertIn("**Stage Details**", rendered)
            self.assertIn("**Codex Execution Layer**", rendered)
            self.assertLess(rendered.index("**AT State Machine**"), rendered.index("**Codex Execution Layer**"))
            self.assertLess(rendered.index("| main"), rendered.index("provider"))

    def test_chat_panel_is_the_empty_at_trigger_view(self) -> None:
        rendered = render_chat_panel([])

        self.assertIn("AT FLOW", rendered)
        self.assertIn("trigger   : AT", rendered)
        self.assertIn("AT STATE MACHINE", rendered)
        self.assertIn("| main     | --> | analysis |", rendered)
        self.assertIn("| standby  |     | standby", rendered)
        self.assertIn("**Command Menu**", rendered)
        self.assertIn("AT: start task, <task>", rendered)
        self.assertIn("**Codex Execution Layer**", rendered)
        self.assertLess(rendered.index("AT STATE MACHINE"), rendered.index("**Codex Execution Layer**"))


if __name__ == "__main__":
    unittest.main()

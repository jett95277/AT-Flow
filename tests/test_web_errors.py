import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.web.errors import ApiError, api_error_response
from at_flow.web.schemas import CommandResultResponse, FileNodeResponse, HealthResponse


class WebErrorContractTests(unittest.TestCase):
    def test_api_error_response_contains_code_message_retryable_and_details(self):
        error = ApiError(
            code="session_not_found",
            message="Unknown session: abc",
            retryable=False,
            details={"session_id": "abc"},
        )

        self.assertEqual(
            api_error_response(error),
            {
                "error": {
                    "code": "session_not_found",
                    "message": "Unknown session: abc",
                    "retryable": False,
                    "details": {"session_id": "abc"},
                }
            },
        )

    def test_api_error_response_omits_none_details(self):
        error = ApiError(
            code="internal_error",
            message="Unexpected failure",
            retryable=False,
        )

        self.assertEqual(
            api_error_response(error),
            {
                "error": {
                    "code": "internal_error",
                    "message": "Unexpected failure",
                    "retryable": False,
                }
            },
        )

    def test_basic_response_schemas_are_dict_serializable(self):
        health = HealthResponse(status="ok", workspace="demo")
        command = CommandResultResponse(ok=True, session={"id": "s1"})
        node = FileNodeResponse(
            name="agent.md",
            path="agents/main/agent.md",
            kind="file",
            children=[],
        )

        self.assertEqual(health.to_dict(), {"status": "ok", "workspace": "demo"})
        self.assertEqual(command.to_dict(), {"ok": True, "session": {"id": "s1"}})
        self.assertEqual(
            node.to_dict(),
            {
                "name": "agent.md",
                "path": "agents/main/agent.md",
                "kind": "file",
                "children": [],
            },
        )


if __name__ == "__main__":
    unittest.main()

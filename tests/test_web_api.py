from pathlib import Path
import os
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient

from at_flow.models import SessionState
from at_flow.transitions import transition_step
from at_flow.web.app import create_app
from at_flow.workspace import ATWorkspace


class WebApiTests(unittest.TestCase):
    def test_health_returns_ok_for_initialized_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.get("/api/health")

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["status"], "ok")
            self.assertEqual(body["workspace"], str(Path(directory).resolve()))

    def test_cors_allows_local_frontend_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.options(
                "/api/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:3000")

    def test_cors_accepts_configured_cloud_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            ATWorkspace.init(Path(directory))
            previous = os.environ.get("AT_ALLOWED_ORIGINS")
            os.environ["AT_ALLOWED_ORIGINS"] = "https://at.example.com,http://localhost:3000"
            try:
                client = TestClient(create_app(directory))
            finally:
                if previous is None:
                    os.environ.pop("AT_ALLOWED_ORIGINS", None)
                else:
                    os.environ["AT_ALLOWED_ORIGINS"] = previous

            response = client.options(
                "/api/health",
                headers={
                    "Origin": "https://at.example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["access-control-allow-origin"], "https://at.example.com")

    def test_health_maps_missing_workspace_to_runtime_not_initialized(self):
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(create_app(directory))

            response = client.get("/api/health")

            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["error"]["code"], "runtime_not_initialized")

    def test_doctor_returns_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.get("/api/doctor")

            self.assertEqual(response.status_code, 200)
            self.assertTrue(any(check["name"] == "config" for check in response.json()["checks"]))

    def test_doctor_returns_provider_capability_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.get("/api/doctor")

            self.assertEqual(response.status_code, 200)
            checks = response.json()["checks"]
            provider_checks = [check for check in checks if check["name"].startswith("provider:")]
            self.assertTrue(any(check["name"] == "provider:mock" and check["ok"] for check in provider_checks))
            self.assertTrue(any(check["name"] == "provider:codex" for check in provider_checks))

    def test_sessions_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.get("/api/sessions")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"sessions": []})

    def test_session_state_returns_existing_session(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                session_id="api-session",
            )
            workspace.create_session(session)
            client = TestClient(create_app(directory))

            response = client.get("/api/sessions/api-session/state")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["id"], "api-session")

    def test_unknown_session_returns_typed_error(self):
        with tempfile.TemporaryDirectory() as directory:
            ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.get("/api/sessions/missing/state")

            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["error"]["code"], "session_not_found")

    def test_trace_audit_and_artifact_endpoints_return_runtime_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="evidence-session",
            )
            workspace.create_session(session)
            client = TestClient(create_app(directory))
            client.post("/api/sessions/evidence-session/continue")

            trace = client.get("/api/sessions/evidence-session/trace")
            audit = client.get("/api/sessions/evidence-session/audit")
            artifact = client.get("/api/sessions/evidence-session/artifact/main")

            self.assertEqual(trace.status_code, 200)
            self.assertTrue(any(event["event"] == "collect_output" for event in trace.json()["trace"]))
            self.assertEqual(audit.status_code, 200)
            self.assertEqual(audit.json()["audit"][0]["agent"], "main")
            self.assertEqual(artifact.status_code, 200)
            self.assertIn("## Task Summary", artifact.json()["artifact"])

    def test_artifact_endpoint_returns_empty_artifact_for_pending_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="pending-artifact-session",
            )
            workspace.create_session(session)
            client = TestClient(create_app(directory))

            response = client.get("/api/sessions/pending-artifact-session/artifact/main")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["artifact"], "")

    def test_workspace_tree_returns_safe_nodes(self):
        with tempfile.TemporaryDirectory() as directory:
            ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.get("/api/workspace/tree")

            self.assertEqual(response.status_code, 200)
            paths = _flatten_paths(response.json()["tree"])
            self.assertIn("agents/main/agent.md", paths)

    def test_file_endpoint_reads_allowed_relative_file(self):
        with tempfile.TemporaryDirectory() as directory:
            ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.get("/api/file", params={"path": "agents/main/agent.md"})

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["path"], "agents/main/agent.md")
            self.assertIn("main", response.json()["content"].lower())

    def test_file_endpoint_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.get("/api/file", params={"path": "../at.config.json"})

            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"]["code"], "file_not_allowed")

    def test_file_endpoint_rejects_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.get("/api/file", params={"path": str(workspace.root / "at.config.json")})

            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"]["code"], "file_not_allowed")

    def test_create_session_endpoint_creates_runtime_session(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.post("/api/sessions", json={"task": "demo", "provider": "mock"})

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["ok"])
            session_id = body["session"]["id"]
            self.assertTrue(workspace.state_path(session_id).exists())

    def test_create_session_accepts_codex_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            client = TestClient(create_app(directory))

            response = client.post("/api/sessions", json={"task": "demo", "provider": "codex"})

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["session"]["provider"], "codex")
            self.assertTrue(workspace.state_path(body["session"]["id"]).exists())

    def test_run_one_step_endpoint_advances_only_first_step(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                session_id="run-one-session",
            )
            workspace.create_session(session)
            client = TestClient(create_app(directory))

            response = client.post("/api/sessions/run-one-session/run-one-step")

            self.assertEqual(response.status_code, 200)
            steps = response.json()["session"]["steps"]
            self.assertEqual(steps[0]["status"], "done")
            self.assertEqual(steps[1]["status"], "queued")

    def test_continue_endpoint_completes_mock_session(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                session_id="continue-session",
            )
            workspace.create_session(session)
            client = TestClient(create_app(directory))

            response = client.post("/api/sessions/continue-session/continue")

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["session"]["status"] == "done")

    def test_retry_endpoint_retries_failed_step(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            session = SessionState.new(
                task="demo",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="retry-session",
            )
            transition_step(session, 0, "running")
            transition_step(session, 0, "failed", error="temporary failure", retryable=True)
            workspace.create_session(session)
            client = TestClient(create_app(directory))

            response = client.post("/api/sessions/retry-session/retry")

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["session"]["steps"][0]["status"], "done")
            self.assertEqual(body["session"]["steps"][0]["retry_count"], 1)


def _flatten_paths(nodes):
    paths = []
    for node in nodes:
        paths.append(node["path"])
        paths.extend(_flatten_paths(node["children"]))
    return paths


if __name__ == "__main__":
    unittest.main()

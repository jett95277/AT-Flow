from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeployTemplateTests(unittest.TestCase):
    def test_nginx_template_serves_frontend_and_proxies_api(self):
        content = (ROOT / "deploy" / "nginx" / "at-flow.conf.example").read_text(encoding="utf-8")

        self.assertIn("server_name example.com", content)
        self.assertIn("root /opt/at-flow/web/dist;", content)
        self.assertIn("location /api/", content)
        self.assertIn("proxy_pass http://127.0.0.1:8000/api/", content)
        self.assertNotIn("E:\\", content)

    def test_systemd_template_runs_backend_on_localhost(self):
        content = (ROOT / "deploy" / "systemd" / "at-flow-backend.service.example").read_text(encoding="utf-8")

        self.assertIn("WorkingDirectory=/opt/at-flow", content)
        self.assertIn("EnvironmentFile=/etc/at-flow/at-flow.env", content)
        self.assertIn("python -m at_flow.web --root /opt/at-flow --host 127.0.0.1 --port 8000", content)
        self.assertNotIn("0.0.0.0", content)
        self.assertNotIn("E:\\", content)

    def test_env_template_contains_no_secrets(self):
        content = (ROOT / "deploy" / "env" / "at-flow.env.example").read_text(encoding="utf-8")

        self.assertIn("AT_ALLOWED_ORIGINS=https://example.com", content)
        self.assertNotIn("OPENAI_API_KEY=", content)
        self.assertNotIn("password", content.lower())


if __name__ == "__main__":
    unittest.main()

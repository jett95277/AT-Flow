from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeployDocsTests(unittest.TestCase):
    def test_deploy_readme_covers_required_cloud_steps(self):
        content = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")

        required = [
            "Ubuntu 24.04 LTS",
            "python3-venv",
            "npm ci",
            "VITE_AT_API_BASE_URL=/api npm run build",
            "systemctl enable at-flow-backend",
            "nginx -t",
            "certbot --nginx",
            "ufw allow 80",
            "ufw allow 443",
            "journalctl -u at-flow-backend",
            "https://example.com/api/health",
            ".at/sessions",
            ".at/shared",
            ".at/projects",
            ".at/web/console.sqlite3",
        ]
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, content)

    def test_root_readme_links_to_deploy_guide(self):
        content = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("deploy/README.md", content)


if __name__ == "__main__":
    unittest.main()

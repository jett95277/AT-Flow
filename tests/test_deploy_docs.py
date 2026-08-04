from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeployDocsTests(unittest.TestCase):
    def test_deploy_readme_covers_required_cloud_steps(self):
        content = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")

        required = [
            "Ubuntu 24.04 LTS",
            "docker compose",
            "auth_basic",
            "htpasswd",
            "DEEPSEEK_API_KEY",
            "AT_CODEX_SANDBOX",
            "certbot --nginx",
            "ufw allow 80",
            "ufw allow 443",
            "8000",
            "at_data",
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

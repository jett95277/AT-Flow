# AT V1.7 Cloud Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AT Flow deployable as a public HTTPS Web Console backed by FastAPI, Nginx, systemd, SQLite persistence, and a safe `mock` provider demo path.

**Architecture:** React is built into static assets and served by Nginx. Nginx reverse proxies `/api/` to FastAPI on `127.0.0.1:8000`; FastAPI remains the only backend adapter around the AT runtime. Deployment assets are templates only: no secrets, no machine-specific Windows paths, and no direct public exposure of backend port `8000`.

**Tech Stack:** Ubuntu 24.04 LTS, Python `>=3.10`, FastAPI, uvicorn, SQLite, React, Vite, TypeScript, Nginx, systemd, Certbot, unittest, Vitest.

## Global Constraints

- V1.7 owns deployment only; it must not claim stable cloud Codex or opencode execution.
- The supported cloud demo provider is `mock`.
- FastAPI must bind to `127.0.0.1:8000` in production examples.
- Public ports are `22`, `80`, and `443`; port `8000` must not be publicly exposed.
- Production frontend API base must support same-origin `/api`.
- Backend CORS origins must be configurable without using wildcard `*`.
- Deployment files must not contain secrets or user-specific absolute Windows paths.
- Runtime data paths `.at/sessions`, `.at/shared`, `.at/projects`, and `.at/web/console.sqlite3` must be called out as persistent data.
- Every code task must add a failing test before implementation.

---

## File Structure

- `src/at_flow/web/app.py`
  - Owns FastAPI app construction and CORS configuration.
  - Add environment-driven allowed origins.

- `tests/test_web_api.py`
  - Add CORS configuration tests.

- `web/src/api/client.ts`
  - Already owns API base URL resolution.
  - Verify same-origin `/api` production value works.

- `web/src/api/client.test.ts`
  - Add API base URL environment tests if current coverage is insufficient.

- `deploy/nginx/at-flow.conf.example`
  - Example Nginx reverse proxy and static frontend config.

- `deploy/systemd/at-flow-backend.service.example`
  - Example systemd service for FastAPI backend.

- `deploy/env/at-flow.env.example`
  - Example environment file with safe non-secret defaults.

- `deploy/README.md`
  - Reproducible cloud deployment guide.

- `README.md`
  - Add concise V1.7 deployment pointer, not the full guide.

- `docs/superpowers/specs/2026-08-02-at-v1-7-cloud-deployment-design.md`
  - Existing design source of truth.

---

### Task 1: Backend Configurable CORS

**Files:**
- Modify: `src/at_flow/web/app.py`
- Test: `tests/test_web_api.py`

**Interfaces:**
- Consumes: `create_app(root: Path | str = ".") -> FastAPI`
- Produces: `_allowed_origins_from_env() -> list[str]`
- Environment variable: `AT_ALLOWED_ORIGINS`
- Default origins:
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`

- [ ] **Step 1: Write failing test for default CORS origins**

Add to `tests/test_web_api.py`:

```python
    def test_cors_uses_safe_local_defaults_when_env_is_unset(self):
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
```

- [ ] **Step 2: Write failing test for configured cloud origin**

Add to `tests/test_web_api.py`:

```python
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
```

If `tests/test_web_api.py` does not import `os`, add:

```python
import os
```

- [ ] **Step 3: Run tests and confirm failure**

Run:

```powershell
python -m unittest tests.test_web_api.WebApiTests.test_cors_uses_safe_local_defaults_when_env_is_unset tests.test_web_api.WebApiTests.test_cors_accepts_configured_cloud_origin
```

Expected: configured cloud origin test fails because `create_app()` currently hard-codes localhost origins.

- [ ] **Step 4: Implement CORS origin parser**

In `src/at_flow/web/app.py`, add:

```python
import os
```

Then add:

```python
_DEFAULT_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def _allowed_origins_from_env() -> list[str]:
    raw = os.environ.get("AT_ALLOWED_ORIGINS", "")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or list(_DEFAULT_ALLOWED_ORIGINS)
```

Change middleware setup to:

```python
allow_origins=_allowed_origins_from_env(),
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m unittest tests.test_web_api.WebApiTests.test_cors_uses_safe_local_defaults_when_env_is_unset tests.test_web_api.WebApiTests.test_cors_accepts_configured_cloud_origin
```

Expected: both tests pass.

---

### Task 2: Frontend Same-Origin Production API Base

**Files:**
- Modify: `web/src/api/client.test.ts`
- Inspect: `web/src/api/client.ts`

**Interfaces:**
- Consumes: `getDefaultApiBaseUrl()`
- Produces verified behavior:
  - defaults to `http://localhost:8000`
  - accepts `VITE_AT_API_BASE_URL=/api`

- [ ] **Step 1: Inspect current API base implementation**

Open `web/src/api/client.ts` and verify whether the API base URL is already:

```ts
return import.meta.env.VITE_AT_API_BASE_URL || "http://localhost:8000";
```

- [ ] **Step 2: Add production `/api` test**

If current tests do not already cover this, add to `web/src/api/client.test.ts`:

```ts
it("uses same-origin api base when VITE_AT_API_BASE_URL is configured", async () => {
  vi.stubEnv("VITE_AT_API_BASE_URL", "/api");
  const { getDefaultApiBaseUrl } = await import("./client");

  expect(getDefaultApiBaseUrl()).toBe("/api");
});
```

If module caching prevents the env stub from taking effect, use this version:

```ts
it("uses same-origin api base when VITE_AT_API_BASE_URL is configured", async () => {
  vi.resetModules();
  vi.stubEnv("VITE_AT_API_BASE_URL", "/api");
  const { getDefaultApiBaseUrl } = await import("./client");

  expect(getDefaultApiBaseUrl()).toBe("/api");
});
```

- [ ] **Step 3: Run test and confirm behavior**

Run:

```powershell
cd web
npm.cmd test -- --run client
```

Expected: tests pass if existing implementation already supports `/api`. If it fails, make the minimal implementation in `web/src/api/client.ts`:

```ts
export function getDefaultApiBaseUrl() {
  return import.meta.env.VITE_AT_API_BASE_URL || "http://localhost:8000";
}
```

- [ ] **Step 4: Run focused frontend test**

Run:

```powershell
cd web
npm.cmd test -- --run client
```

Expected: all client tests pass.

---

### Task 3: Deployment Template Files

**Files:**
- Create: `deploy/nginx/at-flow.conf.example`
- Create: `deploy/systemd/at-flow-backend.service.example`
- Create: `deploy/env/at-flow.env.example`
- Test: `tests/test_deploy_templates.py`

**Interfaces:**
- Produces deployment templates with placeholders:
  - `example.com`
  - `/opt/at-flow`
  - `/opt/at-flow/web/dist`
  - `127.0.0.1:8000`

- [ ] **Step 1: Write failing deployment template tests**

Create `tests/test_deploy_templates.py`:

```python
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
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
python -m unittest tests.test_deploy_templates
```

Expected: fails because deployment template files do not exist.

- [ ] **Step 3: Create Nginx template**

Create `deploy/nginx/at-flow.conf.example`:

```nginx
server {
    listen 80;
    server_name example.com;

    root /opt/at-flow/web/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

- [ ] **Step 4: Create systemd template**

Create `deploy/systemd/at-flow-backend.service.example`:

```ini
[Unit]
Description=AT Flow FastAPI Backend
After=network.target

[Service]
Type=simple
User=atflow
Group=atflow
WorkingDirectory=/opt/at-flow
EnvironmentFile=/etc/at-flow/at-flow.env
ExecStart=/opt/at-flow/.venv/bin/python -m at_flow.web --root /opt/at-flow --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 5: Create env template**

Create `deploy/env/at-flow.env.example`:

```env
AT_ALLOWED_ORIGINS=https://example.com
PYTHONPATH=/opt/at-flow/src
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
python -m unittest tests.test_deploy_templates
```

Expected: all deployment template tests pass.

---

### Task 4: Cloud Deployment Guide

**Files:**
- Create: `deploy/README.md`
- Modify: `README.md`
- Test: `tests/test_deploy_docs.py`

**Interfaces:**
- Produces reproducible deployment instructions for Ubuntu 24.04 LTS.
- Documents persistence paths and smoke tests.

- [ ] **Step 1: Write failing deployment docs test**

Create `tests/test_deploy_docs.py`:

```python
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
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
python -m unittest tests.test_deploy_docs
```

Expected: fails because `deploy/README.md` does not exist and root README does not link it.

- [ ] **Step 3: Create `deploy/README.md`**

Create a deployment guide with these exact sections:

```markdown
# AT Flow Cloud Deployment

## Target Server

Ubuntu 24.04 LTS.

## Install Packages

...

## Clone Repository

...

## Python Backend Setup

...

## Frontend Build

...

## Environment File

...

## systemd Service

...

## Nginx Reverse Proxy

...

## HTTPS

...

## Firewall

...

## Persistent Data

...

## Smoke Tests

...

## Troubleshooting

...

## Rollback

...
```

The guide must include exact commands for:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nodejs npm nginx certbot python3-certbot-nginx sqlite3 ufw
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd web
npm ci
VITE_AT_API_BASE_URL=/api npm run build
sudo systemctl daemon-reload
sudo systemctl enable at-flow-backend
sudo systemctl restart at-flow-backend
sudo nginx -t
sudo certbot --nginx -d example.com
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
journalctl -u at-flow-backend -n 100 --no-pager
curl https://example.com/api/health
```

- [ ] **Step 4: Add root README pointer**

Add a short V1.7 deployment pointer to `README.md`:

```markdown
## Cloud Deployment

V1.7 deployment instructions are in `deploy/README.md`. The supported cloud
demo path is the Web Console with the `mock` provider behind Nginx, HTTPS,
systemd, and SQLite persistence.
```

- [ ] **Step 5: Run focused docs test**

Run:

```powershell
python -m unittest tests.test_deploy_docs
```

Expected: all deployment docs tests pass.

---

### Task 5: Production Build and Local Regression

**Files:**
- No source files unless previous tasks expose defects.

**Interfaces:**
- Consumes completed Tasks 1-4.
- Produces local verification evidence for V1.7.

- [ ] **Step 1: Run backend full tests**

Run:

```powershell
python -m unittest discover -s tests
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend tests**

Run:

```powershell
cd web
npm.cmd test -- --run
```

Expected: all frontend tests pass.

- [ ] **Step 3: Run frontend production build**

Run:

```powershell
cd web
npm.cmd run build
```

Expected: build passes. If Windows sandbox returns `EPERM` while writing `web/dist`, request approval and rerun the same command with elevated permissions. Record the escalation reason in the final report.

- [ ] **Step 4: Run production-style API base build**

PowerShell:

```powershell
cd web
$env:VITE_AT_API_BASE_URL="/api"
npm.cmd run build
```

Expected: build passes with same-origin API base. If Windows sandbox returns `EPERM`, request approval and rerun with elevated permissions.

- [ ] **Step 5: Inspect diff**

Run:

```powershell
git diff --stat
git diff -- src/at_flow/web/app.py tests/test_web_api.py web/src/api/client.ts web/src/api/client.test.ts deploy README.md tests/test_deploy_templates.py tests/test_deploy_docs.py
```

Expected: diff only includes V1.7 deployment changes, design docs, roadmap docs, and this implementation plan.

- [ ] **Step 6: Commit only after user approval**

Do not commit automatically. If the user approves committing, use:

```powershell
git add docs/superpowers/specs/2026-08-02-at-v1-7-cloud-deployment-design.md docs/superpowers/specs/2026-08-02-at-version-roadmap-design.md docs/superpowers/plans/2026-08-02-at-v1-7-cloud-deployment-implementation-plan.md src/at_flow/web/app.py tests/test_web_api.py web/src/api/client.ts web/src/api/client.test.ts deploy README.md tests/test_deploy_templates.py tests/test_deploy_docs.py
git commit -m "feat: add v1.7 cloud deployment support"
```

---

## Self-Review

- Spec coverage: covers cloud server assumptions, frontend `/api`, backend CORS, Nginx, systemd, env templates, deployment guide, persistence paths, and smoke tests.
- Version boundary: V1.7 stays deployment-focused and does not claim stable Codex/opencode cloud execution.
- Placeholder scan: deployment domain uses `example.com` as an explicit example value, not an unknown requirement.
- Type consistency: `_allowed_origins_from_env() -> list[str]`; `getDefaultApiBaseUrl()` remains the frontend API base function.
- Risk left: actual server deployment still requires the user's public domain/IP, SSH access, and DNS/HTTPS state after local implementation is complete.

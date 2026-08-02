# AT V1.7 Cloud Deployment Design

## Goal

V1.7 turns AT Flow from a local Web Console into a deployable cloud demo. The target is a production-style deployment that interviewers can open through a public domain, while AT still keeps clear runtime boundaries, observable state, persistent artifacts, and controlled backend access.

V1.7 is not the version that proves every external code-agent provider works on the cloud server. The first cloud milestone is to make the Web Console, FastAPI backend, AT runtime, SQLite request history, session artifacts, trace, audit, and state machine work reliably behind HTTPS.

## Recommended Server

Use Ubuntu, not CentOS.

Recommended configuration:

```text
OS: Ubuntu 24.04 LTS
CPU: 2 cores
Memory: 4 GB
Disk: 60 GB SSD
Network: 5 Mbps+
Public ports: 22, 80, 443
```

Minimum acceptable configuration:

```text
OS: Ubuntu 24.04 LTS
CPU: 2 cores
Memory: 2 GB
Disk: 40 GB SSD
Network: 3 Mbps+
Public ports: 22, 80, 443
```

Required system packages:

```text
git
python3
python3-venv
python3-pip
nodejs LTS
npm
nginx
certbot
python3-certbot-nginx
sqlite3
ufw
```

## Deployment Architecture

```text
Public user
  |
  | HTTPS :443
  v
Nginx
  |
  |-- /        -> React static build
  |
  |-- /api/*   -> FastAPI backend on 127.0.0.1:8000
                    |
                    v
                 AT Runtime
                    |
                    |-- .at/sessions
                    |-- .at/shared
                    |-- .at/web/console.sqlite3
                    |-- .at/projects
```

Only Nginx listens publicly. FastAPI must bind to localhost:

```text
127.0.0.1:8000
```

Port `8000` must not be opened to the public internet.

## Runtime Components

### Frontend

The React/Vite app is built once and served as static files by Nginx.

Production frontend API base URL:

```text
VITE_AT_API_BASE_URL=/api
```

This avoids hard-coding the cloud domain into the frontend bundle and lets Nginx route all API traffic through the same origin.

### Backend

FastAPI remains the backend adapter around the AT runtime.

Production backend command shape:

```text
python -m at_flow.web --root /opt/at-flow --host 127.0.0.1 --port 8000
```

The backend must support configurable allowed origins:

```text
AT_ALLOWED_ORIGINS=https://your-domain.example
```

For same-origin `/api` deployment, CORS should normally not be needed by the browser, but the backend should still make allowed origins configurable for future separated deployments.

### Process Manager

FastAPI runs under `systemd`:

```text
at-flow-backend.service
```

The service is responsible for:

- starting the backend after reboot
- restarting on failure
- using the Python virtual environment
- setting production environment variables
- writing logs to `journalctl`

### Reverse Proxy

Nginx is responsible for:

- serving `web/dist`
- reverse proxying `/api/` to `127.0.0.1:8000`
- terminating HTTPS
- applying basic request limits
- optionally applying HTTP Basic Auth for demo protection

## Security Boundary

V1.7 must not expose an unauthenticated AT control surface to the public internet.

Minimum acceptable protection:

```text
HTTP Basic Auth at Nginx
```

This is not a full user system. It is a deployment guard suitable for an interview/demo environment.

Secrets must not be committed:

- domain credentials
- Basic Auth password
- OpenAI keys
- Codex tokens
- cloud server SSH keys

If API keys are added later, they must be provided through environment variables or server-side secret files outside Git.

## Data Persistence

The following paths must survive backend restarts and redeploys:

```text
.at/sessions
.at/shared
.at/projects
.at/web/console.sqlite3
```

The first V1.7 deployment can keep data inside the repo working directory on the server, but the deployment document must clearly identify these paths so they can later move to `/var/lib/at-flow`.

Recommended future production path:

```text
/opt/at-flow        application source
/var/lib/at-flow    runtime data
```

V1.7 can defer the `/var/lib` split if doing it would slow down the first successful demo.

## Provider Strategy

V1.7 cloud demo should default to:

```text
mock
```

The Web Console must still show provider selection, including:

```text
mock
auto
codex
opencode
```

However, cloud readiness for `codex` and `opencode` is not guaranteed in V1.7. These providers may require local login state, CLI authentication, non-interactive execution support, or additional sandboxing.

V1.7 should include provider capability visibility before encouraging cloud use of external process providers. At minimum, deployment documentation must state:

- `mock` is the supported cloud demo provider.
- `codex` and `opencode` are experimental on the cloud server until provider capability checks are implemented.
- Failed process providers must surface errors through AT failure artifacts, trace, and Web Console error display.

## Required V1.7 Code Changes

### Frontend Production API Base

Ensure frontend can be built with:

```text
VITE_AT_API_BASE_URL=/api
```

Expected behavior:

- local development can still use `http://localhost:8000`
- production build can use same-origin `/api`
- no local absolute path or localhost API URL is hard-coded into production deployment docs

### Backend Configurable CORS

Current backend CORS is localhost-only. V1.7 must make it configurable through environment variables.

Expected input:

```text
AT_ALLOWED_ORIGINS=https://your-domain.example,http://localhost:3000,http://127.0.0.1:3000
```

Expected behavior:

- if unset, keep safe local defaults
- if set, parse comma-separated origins
- do not use wildcard `*` for production credentials or protected control surfaces

### Deployment Assets

Add deployment files under a dedicated directory:

```text
deploy/
  nginx/at-flow.conf.example
  systemd/at-flow-backend.service.example
  env/at-flow.env.example
  README.md
```

These files are examples/templates. They must not contain secrets or user-specific absolute Windows paths.

### Deployment Documentation

Add a cloud deployment guide that covers:

- server package installation
- repository clone
- Python virtual environment setup
- frontend dependency install and build
- backend service installation
- Nginx reverse proxy setup
- HTTPS with Certbot
- firewall rules
- smoke tests
- rollback basics

## Local Verification Before Cloud

Before touching the server, V1.7 must pass local verification:

```text
python -m unittest discover -s tests
cd web
npm.cmd test -- --run
npm.cmd run build
```

Local integration smoke:

```text
Backend: http://127.0.0.1:8000/api/health
Frontend: http://127.0.0.1:3000/runtime
```

Production-style local smoke should verify that the frontend can be built with:

```text
VITE_AT_API_BASE_URL=/api
```

## Cloud Smoke Tests

After deployment, verify:

```text
GET https://your-domain.example/
GET https://your-domain.example/api/health
GET https://your-domain.example/api/sessions
```

In the Web Console:

- create a `mock` session
- run one step
- continue the session
- inspect state machine
- inspect trace
- inspect audit
- inspect artifact
- open agent/session files from the file tree

Expected result:

```text
The public Web Console can operate the AT runtime through HTTPS without exposing the backend port directly.
```

## Failure Handling

V1.7 must document and handle these failure paths:

- backend service not running
- frontend cannot reach `/api`
- Nginx proxy misconfiguration
- CORS misconfiguration
- SQLite path not writable
- `.at` runtime directory missing
- provider command unavailable
- HTTPS certificate not issued

For the first implementation, failure handling may be a mix of:

- Web Console visible errors
- FastAPI typed API errors
- deployment guide troubleshooting commands
- `journalctl -u at-flow-backend`
- Nginx access/error logs

## Out Of Scope

These are intentionally not required for V1.7:

- full user login system
- multi-tenant access control
- cloud-hosted Codex authentication automation
- Docker/Kubernetes deployment
- managed database migration
- production-grade secret manager
- horizontal scaling
- WebSocket/SSE streaming

## Success Criteria

V1.7 is successful when:

- the app can be deployed on Ubuntu 24.04 LTS
- frontend and backend work through one HTTPS domain
- backend is managed by systemd
- Nginx serves frontend and proxies `/api`
- SQLite and `.at` runtime data persist across backend restarts
- `mock` provider demo works end to end
- public access is protected by at least HTTP Basic Auth
- deployment instructions are reproducible from a fresh server

## Open Risks

- Real `codex` CLI execution on the cloud server may require additional authentication and non-interactive runtime work.
- Current backend errors may need better user-facing messages for deployment misconfigurations.
- If the server has only 2 GB RAM, frontend build may be slower or require swap.
- If no domain is available, HTTPS can be tested only after DNS points to the server.

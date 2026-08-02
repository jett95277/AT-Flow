# AT Flow Cloud Deployment

## Target Server

Ubuntu 24.04 LTS.

Recommended minimum:

```text
2 CPU cores
4 GB memory
60 GB SSD
Public ports: 22, 80, 443
```

## Install Packages

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nodejs npm nginx certbot python3-certbot-nginx sqlite3 ufw
```

## Clone Repository

```bash
sudo mkdir -p /opt/at-flow
sudo chown "$USER":"$USER" /opt/at-flow
git clone https://github.com/jett95277/AT-Flow.git /opt/at-flow
cd /opt/at-flow
git checkout V1.7
```

## Python Backend Setup

```bash
cd /opt/at-flow
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m at_flow.web --root /opt/at-flow --host 127.0.0.1 --port 8000
```

Stop the foreground process after confirming startup. The production backend will run through systemd.

## Frontend Build

```bash
cd /opt/at-flow/web
npm ci
VITE_AT_API_BASE_URL=/api npm run build
```

The production frontend uses same-origin `/api`, so the public browser does not call `localhost:8000`.

## Environment File

```bash
sudo mkdir -p /etc/at-flow
sudo cp /opt/at-flow/deploy/env/at-flow.env.example /etc/at-flow/at-flow.env
sudo nano /etc/at-flow/at-flow.env
```

Example:

```env
AT_ALLOWED_ORIGINS=https://example.com
PYTHONPATH=/opt/at-flow/src
```

Do not put secrets in Git.

## systemd Service

```bash
sudo useradd --system --home /opt/at-flow --shell /usr/sbin/nologin atflow || true
sudo chown -R atflow:atflow /opt/at-flow
sudo cp /opt/at-flow/deploy/systemd/at-flow-backend.service.example /etc/systemd/system/at-flow-backend.service
sudo systemctl daemon-reload
sudo systemctl enable at-flow-backend
sudo systemctl restart at-flow-backend
sudo systemctl status at-flow-backend --no-pager
```

Backend logs:

```bash
journalctl -u at-flow-backend -n 100 --no-pager
```

## Nginx Reverse Proxy

```bash
sudo cp /opt/at-flow/deploy/nginx/at-flow.conf.example /etc/nginx/sites-available/at-flow
sudo nano /etc/nginx/sites-available/at-flow
sudo ln -sf /etc/nginx/sites-available/at-flow /etc/nginx/sites-enabled/at-flow
sudo nginx -t
sudo systemctl reload nginx
```

Replace `example.com` with your real domain before reloading Nginx.

## HTTPS

Point your DNS A record to the server public IP first.

```bash
sudo certbot --nginx -d example.com
sudo nginx -t
sudo systemctl reload nginx
```

## Firewall

```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
sudo ufw status
```

Port `8000` must not be opened publicly.

## Persistent Data

These paths must survive backend restarts and redeploys:

```text
.at/sessions
.at/shared
.at/projects
.at/web/console.sqlite3
```

For V1.7, these paths can remain under `/opt/at-flow`. A future production split can move runtime data to `/var/lib/at-flow`.

## Smoke Tests

```bash
curl https://example.com/api/health
curl https://example.com/api/sessions
```

Browser checks:

```text
https://example.com/
https://example.com/api/health
```

In the Web Console:

```text
create a mock session
run one step
continue the session
inspect state machine
inspect trace
inspect audit
inspect artifact
open files from the workspace tree
```

## Troubleshooting

Backend:

```bash
sudo systemctl status at-flow-backend --no-pager
journalctl -u at-flow-backend -n 100 --no-pager
```

Nginx:

```bash
sudo nginx -t
sudo tail -n 100 /var/log/nginx/error.log
sudo tail -n 100 /var/log/nginx/access.log
```

Local backend health from the server:

```bash
curl http://127.0.0.1:8000/api/health
```

Common causes:

```text
backend service not running
wrong AT_ALLOWED_ORIGINS
web/dist missing
Nginx server_name not changed from example.com
DNS does not point to the server
certificate not issued
.at directory not writable by atflow
```

## Rollback

```bash
cd /opt/at-flow
git log --oneline -5
git checkout <previous-good-commit>
source .venv/bin/activate
pip install -r requirements.txt
cd web
VITE_AT_API_BASE_URL=/api npm run build
sudo systemctl restart at-flow-backend
sudo nginx -t
sudo systemctl reload nginx
```

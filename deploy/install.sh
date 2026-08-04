#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/at-flow}"
ENV_FILE="${ENV_FILE:-/etc/at-flow/at-flow.env}"
HTPASSWD="${HTPASSWD:-/etc/at-flow/.htpasswd}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root or with sudo" >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
  curl -fsSL https://mirrors.cloud.tencent.com/docker-ce/linux/ubuntu/gpg | gpg --batch --yes --dearmor -o /etc/apt/keyrings/docker.gpg
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://mirrors.cloud.tencent.com/docker-ce/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker

cat > /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://docker.m.daocloud.io"
  ]
}
EOF
systemctl restart docker

mkdir -p /etc/at-flow "$APP_DIR/.at"

if [[ ! -f "$ENV_FILE" ]]; then
  AUTH_PASS="${AT_AUTH_PASS:-$(openssl rand -base64 18)}"
  cat > "$ENV_FILE" <<EOF
AT_ALLOWED_ORIGINS=${AT_ALLOWED_ORIGINS:-http://localhost}
PYTHONPATH=$APP_DIR/src
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-}
AT_CODEX_SANDBOX=${AT_CODEX_SANDBOX:-workspace-write}
AT_AUTH_USER=${AT_AUTH_USER:-atflow}
AT_AUTH_PASS=$AUTH_PASS
EOF
  chmod 600 "$ENV_FILE"
fi

if [[ ! -f "$HTPASSWD" ]]; then
  AUTH_USER="$(grep '^AT_AUTH_USER=' "$ENV_FILE" | cut -d= -f2)"
  AUTH_PASS="$(grep '^AT_AUTH_PASS=' "$ENV_FILE" | cut -d= -f2)"
  HASH="$(openssl passwd -apr1 "$AUTH_PASS")"
  printf '%s:%s\n' "$AUTH_USER" "$HASH" > "$HTPASSWD"
  chmod 644 "$HTPASSWD"
fi

cd "$APP_DIR"
docker compose -f deploy/docker-compose.yml up -d --build

ufw allow 22/tcp || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
ufw --force enable || true

echo "deploy complete"
echo "env: $ENV_FILE"
echo "next: run certbot for HTTPS (see deploy/README.md)"

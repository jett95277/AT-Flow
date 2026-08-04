# AT v1.7.1 Cloud Docker Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 把 V1.9 的真实能力（codex/opencode provider、语言契约）通过 Docker Compose 部署到用户已有的 Ubuntu 24.04 服务器，提供 HTTPS + Basic Auth 受控访问，并让真实 provider 在容器内调用 DeepSeek。

**Architecture:** backend 容器（python:3.11-slim + codex/opencode CLI，entrypoint 从 env 生成 provider 配置）+ nginx 容器（多阶段构建托管 dist + Basic Auth + 反代）。certbot 与 docker 守护进程在 host。数据挂 named volume。

**Tech Stack:** Docker Compose v2、python:3.11-slim、nginx:alpine、codex CLI、opencode、rsync/SSH、PowerShell。

## Global Constraints

- 规格来源：`docs/superpowers/specs/2026-08-04-at-v1-7-1-cloud-docker-deployment-design.md`。
- 不改 V1.9 本地双入口与一键脚本行为。
- 密钥（DEEPSEEK_API_KEY、Basic Auth 密码）只存在于服务器 `/etc/at-flow/at-flow.env`，不入 git、不进镜像层。
- codex 沙箱默认 `workspace-write`；容器内不可用时通过 `AT_CODEX_SANDBOX=read-only` 显式切换，不静默降级。
- 8000 不对外；ufw 仅 22/80/443。
- `.at` 数据与 codex/opencode 配置挂 named volume，重启不丢。
- **按用户当前指令：计划与分支统一命名 v1.7.1；开发过程中不 commit/push，最后统一提交。** 每个任务以"记录变更"收尾。
- 本地无 Docker 时，镜像构建类验证标注"未验证（需 Docker）"，不静默当作通过。

---

### Task 1: provider 配置生成模块（可本地单测）

**Files:**
- Create: `src/at_flow/deploy_config.py`
- Test: `tests/test_deploy_config.py`

**Interfaces:**
- Consumes: `at_flow.setup.merge_opencode_config`。
- Produces:
  - `render_codex_config(api_key: str) -> str`：deepseek codex config.toml 文本。
  - `apply_sandbox(config: dict, sandbox: str) -> tuple[dict, bool]`：把 codex 命令的
    `--sandbox` 参数改为给定值，返回 (新 config, 是否变更)。
  - `write_opencode_config(root: Path) -> dict`：基于 merge_opencode_config 生成
    opencode 全局配置 dict。
  - CLI：`python -m at_flow.deploy_config write-codex --key <key>`、
    `apply-sandbox <sandbox> --config <path>`、`write-opencode --root <path> --out <path>`。

- [x] **Step 1: 写失败测试**

```python
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.deploy_config import apply_sandbox, render_codex_config, write_opencode_config


class DeployConfigTests(unittest.TestCase):
    def test_render_codex_config_contains_deepseek_endpoint_and_key(self):
        text = render_codex_config("sk-test")
        self.assertIn("https://api.deepseek.com/", text)
        self.assertIn("experimental_bearer_token = \"sk-test\"", text)

    def test_apply_sandbox_changes_codex_sandbox_flag(self):
        config = {"providers": {"codex": {"command": ["codex", "exec", "--sandbox", "workspace-write", "-"]}}}
        updated, changed = apply_sandbox(config, "read-only")
        self.assertTrue(changed)
        cmd = updated["providers"]["codex"]["command"]
        self.assertEqual(cmd[cmd.index("--sandbox") + 1], "read-only")

    def test_apply_sandbox_noop_when_same(self):
        config = {"providers": {"codex": {"command": ["codex", "exec", "--sandbox", "read-only", "-"]}}}
        updated, changed = apply_sandbox(config, "read-only")
        self.assertFalse(changed)

    def test_write_opencode_config_uses_container_root(self):
        result = write_opencode_config(Path("/opt/at-flow"))
        rules = result["permission"]["external_directory"]
        self.assertIn("/opt/at-flow/.at/shared/**", rules)
        self.assertIn("/opt/at-flow/.at/sessions/**", rules)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: 运行确认失败**

Run: `python -m unittest tests.test_deploy_config -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'at_flow.deploy_config'`

- [x] **Step 3: 最小实现**

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


CODEX_SANDBOX_FLAG = "--sandbox"


def render_codex_config(api_key: str) -> str:
    return f'''model = "deepseek-v4-flash"
model_provider = "deepseek"
preferred_auth_method = "apikey"
forced_login_method = "api"

[model_providers.deepseek]
name = "deepseek"
base_url = "https://api.deepseek.com/"
wire_api = "responses"
experimental_bearer_token = "{api_key}"
'''


def apply_sandbox(config: dict, sandbox: str) -> tuple[dict, bool]:
    from copy import deepcopy

    updated = deepcopy(config)
    command = updated.get("providers", {}).get("codex", {}).get("command")
    if not isinstance(command, list) or CODEX_SANDBOX_FLAG not in command:
        return updated, False
    index = command.index(CODEX_SANDBOX_FLAG)
    if index + 1 < len(command) and command[index + 1] == sandbox:
        return updated, False
    command[index + 1] = sandbox
    return updated, True


def write_opencode_config(root: Path) -> dict:
    from .setup import merge_opencode_config

    return merge_opencode_config(None, root)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="at-deploy-config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    codex = subparsers.add_parser("write-codex", help="write codex config.toml")
    codex.add_argument("--key", required=True)
    codex.add_argument("--out", default="/root/.codex/config.toml")

    sandbox = subparsers.add_parser("apply-sandbox", help="set codex --sandbox in at.config.json")
    sandbox.add_argument("sandbox", choices=["workspace-write", "read-only", "ignore"])
    sandbox.add_argument("--config", required=True)

    opencode = subparsers.add_parser("write-opencode", help="write opencode global config")
    opencode.add_argument("--root", required=True)
    opencode.add_argument("--out", default="/root/.config/opencode/opencode.jsonc")

    args = parser.parse_args(argv)
    if args.command == "write-codex":
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_codex_config(args.key), encoding="utf-8")
        print(f"wrote {path}")
        return 0
    if args.command == "apply-sandbox":
        path = Path(args.config)
        config = json.loads(path.read_text(encoding="utf-8"))
        updated, changed = apply_sandbox(config, args.sandbox)
        if changed:
            path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
        print(f"sandbox={args.sandbox} changed={changed}")
        return 0
    if args.command == "write-opencode":
        data = write_opencode_config(Path(args.root))
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
```

- [x] **Step 4: 运行确认通过**

Run: `python -m unittest tests.test_deploy_config -v`
Expected: PASS（4 个用例）

- [x] **Step 5: 记录变更**

`src/at_flow/deploy_config.py`、`tests/test_deploy_config.py` 待统一提交。

---

### Task 2: backend Dockerfile 与 entrypoint

**Files:**
- Create: `deploy/docker/backend.Dockerfile`
- Create: `deploy/docker/entrypoint.sh`
- Modify: `deploy/.dockerignore`（排除 .git/.at/node_modules/.venv/web/node_modules）

**Interfaces:**
- Consumes: `src/at_flow/deploy_config.py` CLI。
- Produces: backend 镜像，工作目录 `/opt/at-flow`，入口 entrypoint.sh。

- [x] **Step 1: 写 backend.Dockerfile**

```dockerfile
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      nodejs npm curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN npm install -g @openai/codex opencode-ai

WORKDIR /opt/at-flow

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY at.py at.config.json AGENTS.md ./
COPY src ./src
COPY deploy/docker/entrypoint.sh /usr/local/bin/at-entrypoint
RUN chmod +x /usr/local/bin/at-entrypoint

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/at-entrypoint"]
```

- [x] **Step 2: 写 entrypoint.sh**

```bash
#!/bin/sh
set -eu

mkdir -p /root/.codex /root/.config/opencode

if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
  python -m at_flow.deploy_config write-codex --key "$DEEPSEEK_API_KEY" --out /root/.codex/config.toml
fi

SANDBOX="${AT_CODEX_SANDBOX:-workspace-write}"
python -m at_flow.deploy_config apply-sandbox "$SANDBOX" --config /opt/at-flow/at.config.json
python -m at_flow.deploy_config write-opencode --root /opt/at-flow --out /root/.config/opencode/opencode.jsonc

exec python -m at_flow.web --root /opt/at-flow --host 0.0.0.0 --port 8000
```

- [x] **Step 3: 写 deploy/.dockerignore**

```text
.git/
.at/
.venv/
node_modules/
web/node_modules/
web/dist/
output/
.claude/
*.log
```

- [x] **Step 4: 语法验证（无 Docker 时仅做静态检查）**

Run: `bash -n deploy/docker/entrypoint.sh`（本机无 bash 则标注未验证）
Run: `docker build -f deploy/docker/backend.Dockerfile .`（需 Docker，失败/不可用则标注）

- [x] **Step 5: 记录变更**

同上。

---

### Task 3: nginx Dockerfile 与配置模板

**Files:**
- Create: `deploy/docker/nginx.Dockerfile`
- Create: `deploy/docker/nginx.conf.template`

**Interfaces:**
- Consumes: `web/` 前端源码与 `package-lock.json`。
- Produces: nginx 镜像（多阶段构建 dist + auth_basic + 反代）。

- [x] **Step 1: 写 nginx.Dockerfile**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=build /build/dist /usr/share/nginx/html
COPY deploy/docker/nginx.conf.template /etc/nginx/conf.d/default.conf
```

- [x] **Step 2: 写 nginx.conf.template**

```nginx
server {
    listen 80;
    server_name _;

    auth_basic "AT Flow";
    auth_basic_user_file /etc/nginx/.htpasswd;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

- [x] **Step 3: 验证**

Run: `docker build -f deploy/docker/nginx.Dockerfile .`（需 Docker；不可用则标注未验证）

- [x] **Step 4: 记录变更**

同上。

---

### Task 4: docker-compose.yml 与环境模板

**Files:**
- Create: `deploy/docker-compose.yml`
- Modify: `deploy/env/at-flow.env.example`（新增 DEEPSEEK_API_KEY / AT_CODEX_SANDBOX / AT_AUTH_USER / AT_AUTH_PASS）
- Create: `deploy/env/.gitignore`（忽略真实 env）

**Interfaces:**
- Consumes: Task 2/3 镜像。
- Produces: compose 拓扑（backend + nginx + named volumes）。

- [x] **Step 1: 写 docker-compose.yml**

```yaml
services:
  backend:
    build:
      context: ..
      dockerfile: deploy/docker/backend.Dockerfile
    env_file: /etc/at-flow/at-flow.env
    volumes:
      - at_data:/opt/at-flow/.at
      - at_codex:/root/.codex
      - at_opencode:/root/.config/opencode
    expose:
      - "8000"
    restart: unless-stopped

  nginx:
    build:
      context: ..
      dockerfile: deploy/docker/nginx.Dockerfile
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /etc/at-flow/.htpasswd:/etc/nginx/.htpasswd:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  at_data:
  at_codex:
  at_opencode:
```

- [x] **Step 2: 更新 env 模板**

`deploy/env/at-flow.env.example`：

```text
AT_ALLOWED_ORIGINS=https://<domain>
PYTHONPATH=/opt/at-flow/src
DEEPSEEK_API_KEY=<server-only secret>
AT_CODEX_SANDBOX=workspace-write
AT_AUTH_USER=<basic-auth user>
AT_AUTH_PASS=<basic-auth password>
```

`deploy/env/.gitignore`：

```text
at-flow.env
```

- [x] **Step 3: 验证 compose 语法**

Run: `docker compose -f deploy/docker-compose.yml config`（需 Docker；不可用则标注）
Expected: 输出解析后的配置，无错误

- [x] **Step 4: 记录变更**

同上。

---

### Task 5: 服务器一键部署脚本 install.sh

**Files:**
- Create: `deploy/install.sh`

**Interfaces:**
- Consumes: compose 文件、env 模板、nginx 配置。
- Produces: 幂等的服务器部署（docker + env + htpasswd + compose up + certbot + ufw）。

- [x] **Step 1: 写 install.sh**

```bash
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
apt-get install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx rsync
systemctl enable --now docker

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
  openssl passwd -apr1 "$AUTH_PASS" > /tmp/at-htpasswd-entry
  printf '%s:%s\n' "$AUTH_USER" "$(cat /tmp/at-htpasswd-entry)" > "$HTPASSWD"
  rm -f /tmp/at-htpasswd-entry
  chmod 600 "$HTPASSWD"
fi

cd "$APP_DIR"
docker compose -f deploy/docker-compose.yml up -d --build

ufw allow 22/tcp || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
ufw --force enable || true

echo "deploy complete"
echo "env: $ENV_FILE"
echo "check: curl -u \$AT_AUTH_USER http://127.0.0.1/api/health"
```

- [x] **Step 2: 静态检查**

Run: `bash -n deploy/install.sh`（本机无 bash 则标注未验证）
Expected: 无语法错误

- [x] **Step 3: 记录变更**

同上。

---

### Task 6: 本地发布脚本 publish.ps1

**Files:**
- Create: `deploy/publish.ps1`

**Interfaces:**
- Consumes: rsync、ssh。
- Produces: 本地一键同步 + 触发服务器部署。

- [x] **Step 1: 写 publish.ps1**

```powershell
param(
  [Parameter(Mandatory = $true)][string]$HostName,
  [string]$SshUser = "root",
  [string]$AppDir = "/opt/at-flow"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sshTarget = "${SshUser}@${HostName}"

$excludes = @(
  "--exclude", ".git/",
  "--exclude", ".at/",
  "--exclude", "node_modules/",
  "--exclude", "web/node_modules/",
  "--exclude", ".venv/",
  "--exclude", "output/",
  "--exclude", ".claude/"
)

Write-Host "syncing $root -> ${sshTarget}:${AppDir}"
rsync -az --delete $excludes "${root}/" "${sshTarget}:${AppDir}/"

Write-Host "running install.sh on server"
ssh $sshTarget "cd ${AppDir} && bash deploy/install.sh"
```

- [x] **Step 2: 语法检查**

Run: `powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw 'deploy/publish.ps1'))"`（在 PowerShell 内解析）
Expected: 无解析错误

- [x] **Step 3: 记录变更**

同上。

---

### Task 7: 部署文档更新

**Files:**
- Modify: `deploy/README.md`
- Modify: `README.md`（Cloud Deployment 章节指向新流程）

- [x] **Step 1: 重写 deploy/README.md**

覆盖：前置条件（服务器、SSH、DeepSeek key、域名）、`publish.ps1` 首次发布、
`install.sh` 行为、Basic Auth 访问方式、HTTPS（certbot）、无域名降级（IP+HTTP 显式说明）、
升级（重新 publish）、回滚（compose 镜像版本）、日志排查（docker logs）、数据卷说明。

- [x] **Step 2: 更新根 README Cloud Deployment 章节**

指向 `deploy/README.md`，说明 v1.7.1 为 Docker 一键部署、真实 provider 上云。

- [x] **Step 3: 记录变更**

同上。

---

### Task 8: 本地验证与收尾

- [x] **Step 1: 后端全量测试**

Run: `python -m unittest discover -s tests`
Expected: OK（151 + 新增 deploy_config 测试）

- [x] **Step 2: 前端测试与构建**

Run: `npm.cmd test -- --run`；`npm.cmd run build`（workdir `web`）
Expected: 38 通过；build 成功

- [x] **Step 3: Docker 冒烟（如本机有 Docker）**

Run: `docker compose -f deploy/docker-compose.yml build`
Run: 容器内 `curl /api/health` + 创建 mock 会话
Expected: build 成功、health OK、mock 会话闭环
如本机无 Docker：明确标注"镜像构建与容器冒烟未验证，待服务器部署时验证"。

- [x] **Step 4: git 状态核对**

Run: `git status --short`、`git diff --check`
Expected: 无空白错误；真实 env 未被跟踪

- [x] **Step 5: 更新计划状态与汇总**

勾选全部 checkbox，向用户报告改动文件、验证结果、遗留项（服务器实测、codex 沙箱探测、
certbot/DNS），以及部署时需要的输入清单。

## Execution Status

```text
Status: complete
Branch: v1.7.1
Backend tests: 155 passed
Frontend tests: 38 passed
Docker build/smoke: not verified locally (daemon not running); pending server verification
Defects found: nginx build lacked VITE_AT_API_BASE_URL=/api (fixed); env template placeholder contained 'password' (fixed)
```

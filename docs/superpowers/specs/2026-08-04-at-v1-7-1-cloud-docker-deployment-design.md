# AT v1.7.1 Cloud Docker Deployment Design

## Goal

v1.7.1 把 V1.9 的真实能力（codex/opencode provider、语言契约、双入口）部署到
用户已有的 Ubuntu 24.04 云服务器上，采用 Docker Compose 隔离环境，通过
HTTPS + Basic Auth 提供受控的远程 Web Console 访问，并让真实 provider 在
容器内调用 DeepSeek API 执行 code/test 步骤。

本项目定位为个人辅助开发工具流，不是产品。云部署服务于开发者本人：
受控访问、可复现部署、显式降级、可验证。

## Version Boundary

v1.7.1 拥有：

- Docker Compose 部署（backend 容器 + nginx 容器）。
- 服务器一键部署脚本 `deploy/install.sh`（幂等）。
- 本地一键发布脚本 `deploy/publish.ps1`。
- Basic Auth（nginx auth_basic + htpasswd）。
- HTTPS（certbot 或显式降级方案）。
- 容器内 codex / opencode 安装与配置（deepseek provider + 权限规则）。
- codex 容器内沙箱策略（默认 workspace-write，不可用时显式降级开关）。
- 密钥管理（`/etc/at-flow/at-flow.env`，不入 git）。
- 数据持久化（`.at` named volume）。
- 部署文档更新。

v1.7.1 不拥有：

- 多用户/多租户系统。
- 完整 OAuth/SSO。
- provider marketplace。
- 云厂商专有服务（S3、托管 DB 等）。
- 修改本地双入口与一键脚本（V1.9 行为保持）。

## 架构

```text
浏览器
  -> HTTPS :443 (nginx 容器, Basic Auth)
       -> /                静态 web/dist
       -> /api/            反代 backend:8000
          -> backend 容器 (FastAPI + AT Runtime)
             -> provider (容器内 codex CLI / opencode)
                -> https://api.deepseek.com
```

后端与 nginx 均容器化；certbot 与 Docker 守护进程跑在 host。

## 镜像与容器

### backend 镜像（`deploy/docker/backend.Dockerfile`）

- 基础镜像 `python:3.11-slim`。
- 安装 nodejs + npm（用于安装 codex CLI 与 opencode）。
- `npm install -g @openai/codex opencode-ai`（版本以官方最新为准，脚本内固定大版本）。
- `pip install -r requirements.txt`。
- 复制 `src/`、`at.config.json`、`at.py`、`AGENTS.md`。
- entrypoint：从环境变量生成
  - `/root/.codex/config.toml`（deepseek provider，key 来自 `DEEPSEEK_API_KEY`）；
  - `/root/.config/opencode/opencode.jsonc`（deepseek provider + 以 `/opt/at-flow/.at/...`
    为目标的 external_directory 允许规则）；
  然后执行 `python -m at_flow.web --root /opt/at-flow --host 0.0.0.0 --port 8000`。
- 工作目录 `/opt/at-flow`；`.at` 数据挂 named volume。

### nginx 镜像（`deploy/docker/nginx.Dockerfile`）

- 多阶段构建：阶段 1 用 `node:20-alpine` 执行 `npm ci && npm run build`
  产出 `web/dist`；阶段 2 用 `nginx:alpine` 拷贝 dist。
- 配置：`auth_basic` + htpasswd 文件（挂载 `/etc/nginx/.htpasswd`），
  `/api/` 反代 `http://backend:8000`，`try_files` 回退 `index.html`。

### docker-compose.yml

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

`web/dist` 由 nginx 多阶段构建在镜像内产出，不依赖运行时卷。

## 环境变量（`/etc/at-flow/at-flow.env`）

```text
AT_ALLOWED_ORIGINS=https://<domain>
PYTHONPATH=/opt/at-flow/src
DEEPSEEK_API_KEY=<server-only secret>
AT_CODEX_SANDBOX=workspace-write          # 或 read-only（显式降级）
AT_AUTH_USER=<basic-auth user>
AT_AUTH_PASS=<basic-auth password>
```

模板 `deploy/env/at-flow.env.example` 使用占位符；真实文件只在服务器
`/etc/at-flow/`，`.gitignore` 排除（若放在仓库内则用 `deploy/env/.gitignore`）。

## 密钥管理

- `DEEPSEEK_API_KEY` 只存在于服务器 env 文件与容器环境，不写镜像、不进 git。
- Basic Auth 密码由 `install.sh` 生成随机值（或用户指定）写入 env，并用
  `openssl passwd` 生成 htpasswd。
- codex config.toml 与 opencode 配置由容器 entrypoint 从 env 生成，
  属于运行时卷，不入镜像层。

## codex 沙箱策略（显式降级）

- 默认 `AT_CODEX_SANDBOX=workspace-write`，容器内直接尝试。
- 若容器内 codex 沙箱不可用（bubblewrap/setuid 受限），entrypoint 记录错误，
  用户显式设置 `AT_CODEX_SANDBOX=read-only`（或 ignore）后重启容器。
- 降级必须体现在部署文档与 `setup check` 类诊断中，不允许静默回退。

## 部署脚本

### deploy/install.sh（服务器，幂等）

1. 检查 sudo、系统版本（Ubuntu 20.04+/24.04）。
2. 安装 docker、docker compose plugin、nginx、certbot。
3. 创建 `/etc/at-flow/` 与 env 文件（不存在才生成；含随机 Basic Auth 密码）。
4. 生成 `/etc/at-flow/.htpasswd`。
5. 构建并启动：`docker compose up -d --build`。
6. certbot 首次签发（有域名时）与续期 systemd timer。
7. ufw：只开 22/80/443。
8. 输出部署摘要（URL、Basic Auth 用户、健康检查地址）。

### deploy/publish.ps1（本地）

1. 参数：服务器 host、SSH 用户、项目路径（默认 `/opt/at-flow`）。
2. rsync 同步仓库（排除 `.git/`、`.at/`、`node_modules/`、`.venv/`）。
3. SSH 执行 `install.sh`（或仅同步，部署单独执行）。

## 网络安全

- 8000 不对外（compose 仅 expose，nginx 反代）。
- ufw 仅 22/80/443。
- Basic Auth 保护全部页面与 API。

## 数据持久化

- `.at`（sessions/shared/projects/web 的 SQLite）挂 `at_data` 卷，重启不丢。
- codex/opencode 配置挂独立卷，重新部署不丢认证/权限状态。

## 验证门（v1.7.1 完成标准）

1. `install.sh` 在全新服务器上幂等部署成功（连续跑两次无破坏性变更）。
2. `https://<domain>/` 打开 Web Console；未带 Basic Auth 返回 401。
3. `/api/health` 返回 healthy。
4. mock 会话可创建、推进、查看。
5. **真实 codex 会话在容器内跑通**（code/test 步骤调用 deepseek 成功）。
6. `DEEPSEEK_API_KEY` 不出现在 git 与镜像层。
7. 8000 不可从公网访问；重启容器后 `.at` 数据与配置仍在。
8. 部署文档覆盖首次部署、升级、回滚、日志排查。

## 风险与显式降级

- codex 容器内沙箱：默认 workspace-write，失败则显式 `read-only` 开关（不静默）。
- 无域名：降级为 IP + HTTP（Basic Auth 仍在），文档明确说明 HTTPS 缺失风险。
- 服务器到 api.deepseek.com 的网络/防火墙。
- certbot 依赖 DNS 解析；未配置 DNS 时跳过并提示。
- opencode 为可选 provider；服务器上 codex 不可用时不静默切 opencode。

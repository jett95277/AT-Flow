# AT Flow v1.7.1 Cloud Docker Deployment

把 V1.9 的真实能力（codex/opencode provider、语言契约、双入口）部署到
Ubuntu 服务器，通过 HTTPS + Basic Auth 提供受控 Web Console 访问。

## 架构

```text
浏览器 -> HTTPS(nginx 容器, Basic Auth) -> /api/ -> backend 容器(:8000)
                                                      -> codex/opencode
                                                      -> api.deepseek.com
```

## 前置条件

- Ubuntu 服务器（20.04+，推荐 Ubuntu 24.04 LTS），root 或 sudo 权限
- 本地 Windows 机器可 SSH 到服务器
- DeepSeek API key
- 域名（可选；无域名时降级为 IP + HTTP，见下文）

## 首次部署

### 方式一：本地一键发布（推荐）

```powershell
cd E:\AT FLOW
.\deploy\publish.ps1 -HostName <server-ip> -SshUser root
```

脚本会：

1. 用系统 tar 打包项目（排除 `.git`/`.at`/`node_modules`/`.venv` 等）并 SSH 同步
2. 在服务器执行 `deploy/install.sh`

`install.sh` 幂等，会：

1. 安装 docker、docker compose plugin、nginx、certbot（镜像内用 `npm ci` 构建前端）
2. 创建 `/etc/at-flow/at-flow.env`（不存在才生成，含随机 Basic Auth 密码）
3. 生成 `/etc/at-flow/.htpasswd`
4. `docker compose up -d --build`
5. 配置 ufw（22/80/443）

### 方式二：服务器手动执行

```bash
cd /opt/at-flow
bash deploy/install.sh
```

## 环境变量（/etc/at-flow/at-flow.env）

```text
AT_ALLOWED_ORIGINS=https://<domain>
PYTHONPATH=/opt/at-flow/src
DEEPSEEK_API_KEY=<server-only secret>
AT_CODEX_SANDBOX=workspace-write
AT_AUTH_USER=<basic-auth user>
AT_AUTH_PASS=<basic-auth password>
```

- `DEEPSEEK_API_KEY` 只存在于服务器文件，不入 git、不进镜像层
- 修改 env 后重启：`docker compose -f deploy/docker-compose.yml restart backend`
- Basic Auth 密码由 install.sh 首次随机生成；改密码需同时更新 env 与 htpasswd
- nginx 容器使用 `auth_basic` 校验 `/etc/nginx/.htpasswd`，未认证请求返回 401

## HTTPS（certbot）

域名解析指向服务器后：

```bash
apt-get install -y certbot python3-certbot-nginx
certbot --nginx -d <domain>
systemctl enable --now certbot.timer
```

证书路径 `/etc/letsencrypt` 已挂载进 nginx 容器（当前 nginx 模板监听 80；
如需 443 反代，在 `deploy/docker/nginx.conf.template` 补充 443 server 块并重启）。

### 无域名降级（显式说明）

没有域名时只能 IP + HTTP：`AT_ALLOWED_ORIGINS=http://<server-ip>`，
Basic Auth 仍然生效。**风险：明文传输，凭据与 API 流量可被窃听**；
仅建议内网/短期使用，公网使用必须先配置 HTTPS。

## codex 沙箱（显式降级）

容器内 codex 默认 `AT_CODEX_SANDBOX=workspace-write`。若容器内沙箱不可用
（bubblewrap/setuid 受限），backend 日志会出现明确错误；此时可显式设置：

```text
AT_CODEX_SANDBOX=read-only
```

然后 `docker compose restart backend`。这是有意的能力降级，不会静默发生。

## 验证

```bash
curl -u <user>:<password> https://<domain>/api/health
```

浏览器打开 `https://<domain>/`，Basic Auth 弹窗输入账号密码，
创建 mock 会话推进；再创建一个真实任务（codex provider）验证 code/test 步骤。

## 升级

```powershell
.\deploy\publish.ps1 -HostName <server-ip> -SshUser root
```

重复执行幂等；代码变更后重新构建镜像。

## 回滚

```bash
cd /opt/at-flow
docker compose -f deploy/docker-compose.yml down
git checkout <previous-good-commit>
docker compose -f deploy/docker-compose.yml up -d --build
```

## 日志排查

```bash
docker compose -f /opt/at-flow/deploy/docker-compose.yml logs -f backend
docker compose -f /opt/at-flow/deploy/docker-compose.yml logs -f nginx
```

数据卷：`.at` 数据（sessions/shared/projects/SQLite）在 `at_data` 卷，
codex/opencode 配置在 `at_codex`/`at_opencode` 卷；重启不丢。
持久化路径：`.at/sessions`、`.at/shared`、`.at/projects`、`.at/web/console.sqlite3`。

## 安全要点

- 8000 端口不对外（compose 仅 expose，nginx 反代）
- `ufw allow 80/tcp`、`ufw allow 443/tcp`、`ufw allow 22/tcp`，其余默认拒绝
- Basic Auth 保护全部页面与 API
- 密钥只存 `/etc/at-flow/at-flow.env`（600 权限）

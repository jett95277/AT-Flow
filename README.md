# AT Flow

AT Flow 是一个面向工程开发的多 Agent 协作运行时。

它不是简单的 prompt 串联脚本，而是把 `main`、`analysis`、`code`、`test` 四个 Agent 放进受控状态机中，由平台统一管理职责边界、上下文流动、最小权限、artifact、trace、audit 和失败恢复。

Codex、opencode、OpenAI API 或其他执行器在 AT Flow 中都是 provider。AT Flow 负责隔离、调度、记录和验证；成熟 code agent 负责具体工程执行。

## 两种使用方式

AT Flow 保留两种官方入口，它们共享同一个 runtime。

### 1. Codex 对话框模式

用户在 Codex 对话框中触发 AT：

```text
AT
```

或：

```text
AT：帮我实现一个登录模块
```

该模式的原则是：

- AT 状态机先出现
- Codex/provider 能力后出现
- Codex 是执行层，不是流程所有者
- AT 负责 session、状态、权限、handoff、artifact、trace、audit

### 2. Web Console 模式

用户在浏览器中操作 AT：

```text
http://127.0.0.1:3000/runtime
```

Web 前端通过 FastAPI 后端调用同一个 AT runtime：

```text
Web Frontend -> FastAPI Backend -> AT Runtime -> Provider Adapter
```

该模式用于本地演示、状态机可视化、文档查看和运行控制。

## Provider 定位

AT Flow 不应该退化为：

```text
Web Frontend -> FastAPI -> GPT API
```

正确结构是：

```text
Web Frontend / Codex Chat
  -> AT Runtime
  -> Provider Adapter
  -> Codex CLI / opencode / OpenAI API / mock
```

推荐定位：

```text
AT              = runtime / orchestrator
Codex CLI       = preferred mature code-agent provider
opencode        = alternative code-agent provider
OpenAI API      = general LLM provider, translation, summary, lightweight reasoning
mock            = local test provider
```

V1.6 计划会优先强化 Codex provider 和 per-agent provider routing。

## Agent 边界原则

每个 Agent 都有自己的 `agent.md`，但它不应该削弱 Codex 的工程能力。

核心原则：

```text
Codex capability is reused fully.
Agent boundary is enforced strictly.
Role restriction must not become capability degradation.
```

`agent.md` 负责限制：

- 当前 Agent 的职责
- 输入来源
- 输出 artifact 格式
- 不允许越权承担其他 Agent 的工作
- 不确定时如何停止和报告

硬边界由这些机制负责：

- `permissions.json`
- 私有 agent workspace
- `context.json` selected files
- post-run permission audit
- artifact contract validation
- state transition rules

## 当前能力

- 四 Agent 串行状态机：`main -> analysis -> code -> test`
- 每个 Agent 独立 `agent.md`、`permissions.json`、`output.md`
- 每个 Agent 独立 `inbox`、`outbox`、`workspace`
- 多 session 并存，单 session 加锁防止并发推进
- session 级 trace、audit、artifact、error 记录
- 中断恢复、失败 retry、artifact 校验
- 共享文件通过授权文件列表暴露，不直接暴露整个 shared 目录
- 内置 `mock` provider，可在无外部 Agent 环境下做最小闭环测试
- V1.5 Web Console：FastAPI 后端 + React 前端，本地 8000/3000 端口联调

## CLI 使用

安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

在项目根目录运行：

```powershell
python .\at.py init
python .\at.py start "Build a hello-world CLI" --run
python .\at.py list
python .\at.py status <session-id>
python .\at.py trace <session-id>
python .\at.py audit <session-id>
python .\at.py artifact <session-id> main
python .\at.py doctor
```

源码模块方式：

```powershell
$env:PYTHONPATH = "src"
python -m at_flow enable --target "<project-root>"
```

## Web Console 本地启动

后端：

```powershell
$env:PYTHONPATH = "src"
python -m at_flow.web --root . --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd web
npm.cmd install
npm.cmd run dev
```

浏览器打开：

```text
http://127.0.0.1:3000/runtime
```

默认接口地址：

```text
http://localhost:8000
```

## Cloud Deployment

V1.7 deployment instructions are in `deploy/README.md`. The supported cloud
demo path is the Web Console with the `mock` provider behind Nginx, HTTPS,
systemd, and SQLite persistence.

## Web Console 界面

V1.5 控制台优先服务工程演示和调试：

- 左侧显示 session 列表和 AT 工作区文档树
- 中间显示选中文档内容
- 右侧显示运行控制、状态机、trace、audit、artifact
- 状态机显示每个 Agent 的运行状态
- 所有运行操作都通过后端受控 API 触发

当前前端不直接编辑、删除、上传文件，也不保存 API key。

## 测试

后端测试：

```powershell
python -m unittest discover -s tests
```

前端测试：

```powershell
cd web
npm.cmd test -- --run
```

前端构建：

```powershell
cd web
npm.cmd run build
```

浏览器验证使用 Playwright。首次运行前需要安装浏览器：

```powershell
cd web
npx.cmd playwright install chromium
```

## 目录说明

```text
src/at_flow/          AT Flow Python runtime
src/at_flow/web/      FastAPI Web Console backend
tests/                Python unit and sandbox tests
web/                  React Web Console frontend
docs/                 设计文档和开发计划
agent.md              当前开发规则、阶段和节点记录
```

运行时数据默认在 `.at/` 下生成，该目录不进入 Git。

## 当前边界

- V1.5 Web Console 使用轮询，不是 WebSocket 实时推送
- SQLite 只记录 Web 请求历史和本地元数据，不承担复杂业务状态
- Codex/opencode process provider 已有配置雏形，但生产级非交互执行还需要 V1.6 强化
- OpenAI API 可作为 provider 接入，但不应默认替代 Codex code-agent provider
- 前端目前是本地演示控制台，不是多人权限系统
- 部署到云服务器前需要补充生产配置、反向代理、鉴权和日志策略

## pip 代理问题

如果 Windows 环境下 pip 走本地代理时出现：

```text
ValueError: check_hostname requires server_hostname
```

可尝试显式设置 pip 代理协议为 HTTP：

```powershell
python -m pip config set global.proxy http://127.0.0.1:7890
```

这个配置会写入当前用户的 pip 配置，不属于 AT Flow 项目文件。

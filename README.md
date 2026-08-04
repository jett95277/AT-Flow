# AT Flow

AT Flow 是一个面向工程开发的多 Agent 协作运行时。

项目定位是**个人辅助开发工具流**（personal assistive development workflow），
不是产品。它不为大众用户设计，不追求产品化包装或面向用户的内容；所有功能
决策以开发者本人的实际工作流效率、行为可解释性和结果可验证性为准。界面与
文档的取舍（例如中文展示）服务于使用者本人的习惯，而不是假想的产品用户。

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

V1.6 已完成 Codex provider 路由和双入口契约；V1.8 在此基础上补齐
provider 可用性诊断与中英文语言链路。

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
- 角色定义位于 `.at/agents`，不与 `.at/shared` 共享知识区混放
- V1.8 语言契约：中文输入、英文运行与交接、中文前端展示
- 输入和展示翻译状态、provider、错误均写入 `language.json`
- 翻译规则由 `language-translation` Skill 承载（`.at/shared/skills/`），
  输入翻译和展示翻译每次调用时自动加载
- Agent 固定文档提供审核过的中文展示副本（`agent.zh.md`、`output.zh.md`），
  前端默认显示中文，JSON 配置保持英文
- 内置 `mock` provider，可在无外部 Agent 环境下做最小闭环测试
- V1.5 Web Console：FastAPI 后端 + React 前端，本地 8000/3000 端口联调

## Agent 目录与共享区

```text
.at/agents/                 平台级 Agent 角色包
  main|analysis|code|test/
    agent.md
    permissions.json
    output.md

.at/shared/                 跨 Session 共享知识
  memory/
  skills/
  policies/
  docs/
  inbox/

.at/sessions/<id>/agents/   当前 Session 的角色快照和私有工作区
```

`.at/agents` 是平台控制面，`.at/shared` 是受授权读取的知识面，两者不再
混放。旧目录可先预览再显式迁移：

```powershell
python .\at.py migrate-agent-layout
python .\at.py migrate-agent-layout --apply
```

## 中英文语言契约

当前工作区使用以下路径：

```text
中文任务 -> Codex 翻译 -> 英文 task_runtime
         -> 四 Agent 英文 prompt/context/artifact/handoff
         -> Codex 翻译 -> 中文 artifact.zh.md -> Web Console
```

英文 `artifact.md` 是唯一的下游交接文件；中文 `artifact.zh.md` 只用于
前端展示。输入翻译失败会阻止 Agent 运行并允许重试；展示翻译失败不会
伪装成功，前端会明确显示错误并把英文原文放在标注区域中。

`prompt-language-policy` Skill 只定义语言策略；翻译执行规则由
`language-translation` Skill（`SKILL.md` + `glossary.md`）承载。
`LanguageService` 在输入翻译和展示翻译时加载该 Skill 作为指令前缀，
真正的 provider 调用、状态、重试和产物仍由 `LanguageService` 管理。
Skill 缺失时抛 `translation_skill_missing`，不会回退到硬编码指令。
当前 Codex 翻译使用非交互 `codex exec`、只读临时沙箱和 180 秒独立超时。
语言转换会增加调用次数和 token 消耗，网络异常也会增加延迟。

固定文档（Agent 的 `agent.md`、`output.md`）通过审核过的静态中文副本
（`agent.zh.md`、`output.zh.md`）展示：文档 API 默认返回中文副本，
`language=en` 返回英文原文，文档树隐藏副本文件，零运行时翻译成本。

Windows process provider 会识别 npm/fnm 生成的 `.cmd` 启动器，统一使用
UTF-8 收发文本，并在超时时终止整棵子进程树。硬中断遗留的 Session 锁会
通过死 PID 检查回收，活进程锁不会被抢占。

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

## 前置准备

AT Flow 运行时需要 Python >= 3.9 与 Node.js >= 18；code-agent provider
（codex / opencode）需要单独安装并配置模型 API。

### 1. Python 与 Node

```powershell
python --version   # >= 3.9
node --version     # >= 18
```

### 2. codex（默认 code/test provider）

安装 Codex CLI（官方安装方式），然后配置 DeepSeek 模型。编辑
`~/.codex/config.toml`：

```toml
model = "deepseek-v4-flash"
model_provider = "deepseek"
preferred_auth_method = "apikey"
forced_login_method = "api"

[model_providers.deepseek]
name = "deepseek"
base_url = "https://api.deepseek.com/"
wire_api = "responses"
experimental_bearer_token = "<YOUR_DEEPSEEK_API_KEY>"
```

将 `<YOUR_DEEPSEEK_API_KEY>` 替换为你的 DeepSeek API key。

### 3. opencode（可选替代 provider）

```powershell
npm install -g opencode-ai
opencode login
```

`setup.cmd install` 会自动写入 opencode 全局配置（deepseek 模型 +
本项目 `.at/shared` / `.at/sessions` 的外部目录权限）；API key 请通过
`opencode login` 或 `DEEPSEEK_API_KEY` 环境变量提供。

### 4. 未配置 API key 时的降级路径

AT 本体与 `mock` provider 不依赖任何 API。只想先跑通流程时，把
`at.config.json` 中的 `agent_providers` 全部改为 `mock`，或创建会话时
选择 `mock`。`setup.cmd check` 会明确提示 codex/opencode 缺失，不会静默
替换为 mock。

## 一键配置（V1.9）

从零配置整个 AT Flow（环境体检、依赖安装、Codex 对话触发、Provider 命令与
opencode 全局配置补全）以及双入口启动：

```powershell
python scripts/setup.py check     # 环境体检（只读）
python scripts/setup.py install   # 依赖 + 初始化 + 触发块 + 配置补全
python scripts/setup.py start     # 启动后端(:8000) 与前端(:3000) 并打开浏览器
python scripts/setup.py doctor    # 健康自检与双入口就绪说明
```

或一步到位：

```powershell
setup.cmd all
```

脚本幂等，可重复执行，不覆盖已有的 `at.config.json`、`AGENTS.md`、
opencode 全局配置与 `.at/` 数据。

## Cloud Deployment

v1.7.1 deployment instructions are in `deploy/README.md`. The cloud path runs
the full V1.9 capability (codex/opencode providers, language contract) inside
Docker containers behind Nginx, HTTPS, and Basic Auth.

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
- Codex 可用性诊断和受限翻译调用已经验证；完整工程写入仍受 Agent 权限、Codex sandbox 与项目路径授权共同限制
- OpenAI API 可作为 provider 接入，但不应默认替代 Codex code-agent provider
- 当前 Codex 翻译遇到 WebSocket 超时时会由 Codex CLI 明确降到 HTTPS；本次实测成功，但耗时显著增加
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

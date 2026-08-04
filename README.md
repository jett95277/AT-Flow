# AT Flow

AT Flow 是一个面向 AI-native software development 的多智能体协作运行时。

它不是简单的 prompt 编排脚本，也不是把几个 Agent 串起来聊天的 demo。AT Flow 的目标是把 Codex、opencode、Claude Code 等成熟 Code Agent 放进一个受控运行时中，让多个 Agent 在清晰的职责边界、上下文边界和权限边界内协作。

> Code Agent 负责产出，AT Flow 负责流程、边界、上下文、权限和证据。

## Why AT Flow

AT Flow 来自我自己使用 Code Agent 做工程开发时遇到的真实问题。

在小项目里，直接使用 Codex、Claude Code 或其他 Code Agent 往往已经足够：把需求交给 Agent，让它读代码、改代码、跑测试，很多事情可以很快完成。

但当项目规模变大后，单独使用一个 Code Agent 很容易失控：

- 上下文越来越混乱，任务目标、历史决策、当前代码状态混在一起；
- Agent 容易一边分析、一边实现、一边验证，职责边界变得模糊；
- 多开几个 Codex 也不能自然形成协作，因为它们之间没有稳定的状态机、handoff 和共享记忆治理；
- 如果 Agent 改错文件、污染上下文、遗漏验证，很难追踪问题发生在哪一步；
- 长期使用下来，真正的瓶颈不是 Agent 能不能写代码，而是如何让强 Agent 在可控边界内协作。

AT Flow 就是为了解决这个问题而做的个人开发平台。

目前它仍然是一个串行的 Agent 流水线：`main -> analysis -> code -> test`。这个设计不追求一开始就做复杂并行调度，而是先把职责边界、上下文隔离、artifact handoff、权限审计和失败记录做扎实。对个人工程开发来说，这已经能显著降低 Code Agent 使用中的混乱感。

## What Is AT Flow

AT Flow 是一个外层 runtime / orchestrator。

它不会替代 Codex、opencode 或 Claude Code，而是把这些 Code Agent 作为 provider 接入，由 AT Flow 统一管理：

- session 状态
- Agent 职责边界
- 上下文构造
- 文件流转
- artifact 契约
- 权限审计
- trace 和 failure 记录
- retry 与中断恢复

推荐理解方式：

```text
User / Codex Chat / CLI
  -> AT Flow Runtime
  -> main -> analysis -> code -> test
  -> Provider Adapter
  -> Codex CLI / opencode / Claude Code / OpenAI API / mock
```

## Agent Pipeline

AT Flow 默认包含四个 Agent：

```text
main -> analysis -> code -> test
```

### main

负责理解用户意图、任务边界、目标、非目标、约束和验收标准。默认不改代码、不跑测试。

### analysis

负责项目理解、方案拆解、风险判断、执行计划和测试策略。默认可读项目，但不修改项目。

### code

负责实际实现和变更说明。默认是唯一允许修改共享项目的 Agent。

### test

负责验证、测试证据、失败报告和残余风险判断。默认可读项目，但不修生产代码。

## Core Runtime Contracts

AT Flow 的核心不是界面，而是一组运行时契约。

### `context.json`

每个 Agent 执行前，AT Flow 会生成专属上下文契约，只暴露当前 Agent 被授权看到的内容。

### `artifact.md`

Agent 之间不共享可变对话上下文，而是通过结构化 artifact 交接结果。

### `permissions.json`

每个 Agent 拥有独立权限定义。默认最小权限，必要能力显式授予。

### `handoff/`

AT Flow 负责把上一个 Agent 的 artifact 路由给下一个 Agent。Agent 不直接写入其他 Agent 的目录。

### `trace.jsonl`

记录每个运行节点，例如 context 构造、provider 执行、输出收集、权限审计和状态迁移。

### `audit/`

记录权限审计结果，用于发现 Agent 是否修改了不该修改的路径。

### `failure.json`

当 provider 失败、artifact 不满足契约或权限审计失败时，AT Flow 会写入结构化失败记录。

## Current Features

当前版本已经支持：

- 四 Agent 串行状态机：`main -> analysis -> code -> test`
- 多 session 并存
- 单 session 加锁，避免并发推进同一个 session
- 每个 Agent 独立 `agent.md`、`permissions.json`、`output.md`
- 每个 Agent 独立 `inbox`、`outbox`、`workspace`
- agent package 在 session 创建时快照化
- provider 默认在当前 Agent 私有 workspace 中运行
- `context.json` selected files 授权机制
- artifact contract 校验
- permission audit
- trace / audit / artifact / doctor CLI
- provider failure 结构化记录
- retry 和中断恢复
- memory proposal 收集机制
- mock provider，用于无外部 Code Agent 环境下测试
- Codex / opencode provider 配置雏形

## Quick Start

初始化 AT 工作区：

```powershell
python .\at.py init
```

启动一个任务并运行完整流水线：

```powershell
python .\at.py start "Build a hello-world CLI" --run
```

查看 session：

```powershell
python .\at.py list
python .\at.py status <session-id>
```

查看运行证据：

```powershell
python .\at.py trace <session-id>
python .\at.py audit <session-id>
python .\at.py artifact <session-id> main
python .\at.py doctor
```

源码模块方式启用到目标项目：

```powershell
$env:PYTHONPATH = "src"
python -m at_flow enable --target "<project-root>"
```

安装成 Python 包后：

```powershell
at enable --target "<project-root>"
```

## Deployment / Local Development

AT Flow 当前 main 分支以本地 CLI/runtime 使用为主。
### 云端演示环境（v1.7 云部署）

公网访问地址：`http://175.178.228.21`

- Web Console 通过浏览器访问，Basic Auth 保护（凭据配置在服务器 `/etc/at-flow/at-flow.env`）
- 部署方式：Docker Compose（backend + nginx 容器），详见 `deploy/README.md`
- 说明：裸 IP 无法签发 HTTPS 证书，当前为 HTTP + Basic Auth；公网长期使用建议绑定域名后启用 HTTPS

安装为可编辑包：

```powershell
python -m pip install -e .
```

初始化并运行：

```powershell
at init
at start "Build a hello-world CLI" --run
```

如果使用源码方式运行：

```powershell
$env:PYTHONPATH = "src"
python .\at.py init
python .\at.py start "Build a hello-world CLI" --run
```

provider 配置位于：

```text
at.config.json
```

默认内置 `mock` provider，便于在没有外部 Code Agent 的环境下验证 runtime 闭环。Codex 和 opencode provider 已预留 process 配置，后续会继续强化非交互执行、per-agent routing 和 provider capability detection。

## Test

运行后端测试：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
```

编译检查：

```powershell
python -m compileall src tests at.py
```

## Project Structure

```text
src/at_flow/          AT Flow Python runtime
tests/                Python unit and sandbox tests
docs/                 design docs and development notes
at.py                 local CLI entry
at.config.json        AT workspace config
```

运行时数据默认生成在 `.at/` 下，该目录不进入 Git。

## Project Status

AT Flow 当前是一个可运行的个人 Agent 开发平台，也是一个多智能体工程治理 runtime 的实验原型。

它已经可以用于本地开发、流程演示和 Agent 协作实验，但还不是生产级多租户平台。当前隔离模型主要是“最小环境 + 私有 workspace + 路径级审计”，可以发现越权和降低误操作风险，但还不是 OS 级强隔离。

## Roadmap

### Near Term

- 强化 Codex provider
- 支持 per-agent provider routing
- 改进 Codex / opencode 非交互执行适配
- 强化 artifact validation
- 增加更完整的 provider capability detection
- 增强 CLI / conversation control panel 展示

### Mid Term

- 接入 opencode、Claude Code 等 Code Agent provider
- 接入 OpenAI Agents SDK 作为可选 provider/runtime layer
- Web Console：FastAPI backend + React frontend
- memory proposal review / merge 流程
- 更强的文件权限 enforcement
- Agent 级运行耗时、token、成本和失败类型统计

### Long Term

- DAG / 并行 Agent workflow
- 多 session 并发调度
- 团队级 Agent 工作台
- 可审计的 shared memory / shared skills governance
- 面向真实工程组织的 AI-native development runtime

## Design Principles

- Agent 负责产出，AT Flow 负责治理
- 职责边界必须写入 Agent contract
- 上下文必须显式构造，不能依赖模型自觉
- Agent 之间只通过 artifact handoff 协作
- shared memory 默认不能被 Agent 直接修改
- 默认最小权限，必要能力显式授予
- 每一步运行都必须留下 trace、artifact、audit 或 failure 证据
- 先做可靠 runtime，再做漂亮控制台

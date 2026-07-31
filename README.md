# AT Flow

开发 AT Flow 的工程原则见 [docs/developing-at.md](docs/developing-at.md)。
终极实施计划中文版见 [docs/superpowers/plans/2026-07-31-at-runtime-development-plan.zh.md](docs/superpowers/plans/2026-07-31-at-runtime-development-plan.zh.md)。
英文版见 [docs/superpowers/plans/2026-07-31-at-runtime-development-plan.md](docs/superpowers/plans/2026-07-31-at-runtime-development-plan.md)。

AT Flow 不是一个简单的多 agent prompt 编排脚本，而是一个面向 CLI agent 的隔离式协作运行时。

它把 Codex、opencode 等外部 agent 作为可替换的执行 provider，把 `main`、`analysis`、`code`、`test` 四个角色放进同一个受控状态机里，并由平台脚本统一管理任务状态、职责边界、文件流转、最小权限和越权审计。

AT 的目标是让强能力 agent 能参与真实项目开发，但不把项目安全完全交给模型自觉：agent 负责产出，AT 负责隔离、调度、搬运、校验和记录。

## Codex 对话框模式

AT 的主入口应该是 Codex 对话框，而不是用户手动操作终端。

理想使用方式是用户在 Codex 对话框里说：

```text
AT：开始一个任务，帮我实现 xxx
```

如果用户只输入：

```text
AT：
```

Codex 不应该回复普通闲聊，而应该直接打开 AT ASCII 启动界面：

```powershell
python .\at.py panel --format chat
```

启动界面展示 AT 标识、四 agent 状态机、当前会话和命令菜单，不创建 session。

然后 Codex 作为 AT 的外层控制器，在后台调用 AT runtime：

```powershell
python .\at.py start "帮我实现 xxx" --format chat
python .\at.py run <session-id> --one-step --format chat
```

每推进一个 agent，Codex 对话框里先显示 AT 状态机：

```text
main[done] -> analysis[running] -> code[queued] -> test[queued]
```

也就是说：

- 用户留在 Codex 对话框里发需求
- AT 负责创建 session、推进状态机、隔离 agent、路由 handoff
- Codex 对话框负责展示当前状态、关键产物和下一步，但展示顺序必须服从 AT
- CLI 是后台执行器和调试入口，不是主要用户界面

对话框中推荐使用 ASCII 控制台结构，且必须先出现 AT 状态机，再出现 Codex/provider 能力：

**AT Control Panel**

**AT State Machine**
```text
+----------+     +----------+     +----------+     +----------+
| main     | --> | analysis | --> | code     | --> | test     |
| done     |     | running  |     | queued   |     | queued   |
+----------+     +----------+     +----------+     +----------+
```

**Current Stage**
```text
session : <session-id>
task    : ...
project : ...
agent   : analysis
state   : running
role    : plan and risk
input   : agents/main/outbox/artifact.md
output  : agents/analysis/outbox/artifact.md
```

**Stage Details**
```text
+----------+---------+----------------+--------------------------------------+
| agent    | state   | role           | artifact                             |
+----------+---------+----------------+--------------------------------------+
| main     | done    | task boundary  | agents/main/outbox/artifact.md       |
| analysis | running | plan and risk  | generating                           |
| code     | queued  | implementation | waiting                              |
| test     | queued  | verification   | waiting                              |
+----------+---------+----------------+--------------------------------------+
```

**Codex Execution Layer**
```text
provider : mock
role     : executor controlled by AT state machine
boundary : agent.md + permissions.json + output.md
```
不要把 Codex 能力说明放在状态机之前。AT 是对话框里的流程主体，Codex 是执行层。

## 当前状态

已实现最小可运行版本：

- 四 agent 串行状态机：`main -> analysis -> code -> test`
- 多 session 并存
- session 级锁，防止同一个 session 被两个 runner 同时推进
- 每个 agent 独立 `agent.md`、`permissions.json`、`output.md`
- 每个 agent 独立 `inbox`、`outbox`、`workspace`
- provider 默认在当前 agent 的私有 `workspace` 中执行
- handoff 由 AT 复制，不允许 agent 直接写入其他 agent 目录
- 默认最小环境变量，不暴露 workspace root、shared root、session root
- 每个 agent 执行前生成专属 `context.json`
- `context.json` 通过 `selected_files` 暴露授权 shared 文件，不暴露 shared 目录
- 长期记忆更新先进入 session 级 `memory-proposals`
- 路径级权限审计
- 内置 `mock` provider，便于无外部 CLI 时测试
- 预留 Codex 和 opencode provider 配置

## CLI 调试入口

```powershell
python .\at.py init
python .\at.py start "Build a hello-world CLI" --run
python .\at.py list
python .\at.py status <session-id>
```

## 一键启用

源码模式：

```powershell
$env:PYTHONPATH = "src"
python -m at_flow enable --target "<project-root>"
```

安装为 Python 包后：

```powershell
at enable --target "<project-root>"
```

如果已经在目标项目根目录中，也可以使用：

```powershell
at enable --target .
```

`enable` 会在目标项目中完成两件事：

- 初始化 `at.config.json` 和 `.at/`
- 写入 `AGENTS.md` 的 AT 触发规则

然后在目标项目中重启 Codex，输入：

```text
AT
```

Codex 应显示 AT ASCII 控制面板。

常用调试命令：

```powershell
python .\at.py init
python .\at.py panel --format chat
python .\at.py start "任务描述"
python .\at.py start "任务描述" --run
python .\at.py start "任务描述" --run --format chat
python .\at.py run <session-id>
python .\at.py run <session-id> --one-step
python .\at.py retry <session-id> --format chat
python .\at.py run <session-id> --one-step --format chat
python .\at.py status <session-id>
python .\at.py status <session-id> --format chat
python .\at.py list
python .\at.py list --format chat
python .\at.py trace <session-id>
python .\at.py audit <session-id>
python .\at.py artifact <session-id> <agent>
python .\at.py doctor
```

## 四个 Agent

`main`

负责用户意图、任务边界、目标、非目标、约束和验收标准。默认不写代码、不跑测试、不改项目文件。

`analysis`

负责方案分析、项目理解、风险判断、执行计划和测试策略。默认可读项目，但不可修改项目。

`code`

负责实际实现和变更说明。默认是唯一允许修改共享项目的 agent，但仍禁止直接修改 shared memory、skills、policies 和其他 agent 目录。

`test`

负责验证、测试证据、失败报告和残余风险判断。默认可读项目，但不可修生产代码。

## 工作区结构

```text
.at/
  shared/
    agents/
      main/
        agent.md
        permissions.json
        output.md
      analysis/
        agent.md
        permissions.json
        output.md
      code/
        agent.md
        permissions.json
        output.md
      test/
        agent.md
        permissions.json
        output.md
    memory/
    skills/
    policies/
    docs/
    inbox/
    proposals/
  projects/
  sessions/
    <session-id>/
      state.json
      .lock
      audit/
      context/
      handoff/
      memory-proposals/
      agents/
        main/
          agent.md
          permissions.json
          output.md
          context.json
          prompt.md
          inbox/
          outbox/
          workspace/
```

共享 agent package 位于：

```text
.at/shared/agents/<agent>/
```

创建 session 时，AT 会把共享 package 复制到 session 内：

```text
.at/sessions/<session-id>/agents/<agent>/
```

这意味着旧 session 使用的是当时的 agent contract 快照，不会被后续共享模板修改影响。

## Agent Package

每个 agent package 包含三个核心文件：

`agent.md`

定义 agent 的任务使命、负责范围、禁止事项、输入和输出要求。

`permissions.json`

定义该 agent 的读写权限。运行后审计会根据这里的规则判断是否越界。

`output.md`

定义该 agent 应该写入 `outbox/artifact.md` 的报告结构。

## Runtime 流程

AT 每一步都由平台脚本推进：

```text
prepare_agent
route_prior_handoff
build_context
run_agent
collect_output
collect_memory_proposals
audit_permissions
route_handoff
update_state
```

agent 不直接推进状态机，也不直接复制文件给下一个 agent。

handoff 示例：

```text
main/outbox/artifact.md
  -> handoff/00-main-artifact.md
  -> analysis/inbox/00-main-artifact.md

analysis/outbox/artifact.md
  -> handoff/01-analysis-artifact.md
  -> code/inbox/01-analysis-artifact.md
```

## 沙箱与最小权限

process provider 默认使用：

```json
{
  "cwd": "workspace",
  "env_policy": "minimal"
}
```

provider 默认只获得当前 agent 所需的环境变量：

```text
AT_SESSION_ID
AT_AGENT
AT_AGENT_DIR
AT_INBOX
AT_OUTBOX
AT_AGENT_WORKSPACE
AT_PERMISSIONS
AT_OUTPUT_CONTRACT
AT_CONTEXT
AT_PROJECT_PATH
AT_SHARED_MEMORY
AT_SHARED_SKILLS
AT_SHARED_INBOX
```

其中：

- `AT_PROJECT_PATH` 只在 agent 拥有项目访问权限时传入
- `AT_CONTEXT` 指向当前 agent 的专属上下文契约
- `AT_SHARED_MEMORY`、`AT_SHARED_SKILLS`、`AT_SHARED_INBOX` 保留为空值，不再暴露 shared 目录
- 授权的 shared memory、skills、policies、docs、inbox 文件必须从 `AT_CONTEXT` 的 `selected_files` 读取
- 默认不传 `AT_WORKSPACE_ROOT`
- 默认不传 `AT_SHARED_ROOT`
- 默认不传 `AT_SESSION_DIR`

当前沙箱是“最小环境 + 私有 cwd + 路径级审计”。它能发现越权和降低误操作风险，但还不是 OS 级强隔离。后续可以继续接入 Windows ACL、独立 worktree、受控文件代理或更强的进程沙箱。

## 权限审计

每个 agent 执行前后，AT 会对受保护区域做路径快照对比：

- `.at/shared`
- 共享项目路径
- 其他 agent 目录
- `state.json`
- `handoff`

默认策略：

- `main` 不允许写项目
- `analysis` 不允许写项目
- `code` 允许写项目
- `test` 不允许写项目
- 所有 agent 默认不允许直接写 shared
- 所有 agent 默认不允许写其他 agent 目录
- 所有 agent 默认不允许写 session 控制文件

审计报告位于：

```text
.at/sessions/<session-id>/audit/
```

## Provider 配置

provider 配置位于 `at.config.json`。

示例：

```json
{
  "providers": {
    "codex": {
      "type": "process",
      "command": ["codex"],
      "prompt_mode": "stdin",
      "cwd": "workspace",
      "env_policy": "minimal",
      "env_passthrough": [
        "PATH",
        "PATHEXT",
        "SystemRoot",
        "ComSpec",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "LANG"
      ],
      "timeout_seconds": 1800
    }
  }
}
```

`prompt_mode` 支持：

- `stdin`：将 prompt 写入标准输入
- `arg`：将 prompt 作为最后一个命令参数
- `file`：将 prompt 写入 `prompt.md`，并把文件路径作为参数传入

只有 provider 确实需要完整父进程环境时，才应使用：

```json
{
  "env_policy": "inherit"
}
```

## 测试

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
python -m compileall src tests at.py
```

当前测试覆盖：

- mock provider 跑通完整四 agent 流程
- session 内 agent package 快照
- `inbox/outbox/workspace` 物理目录生成
- handoff 文件路由
- audit 报告生成
- `main` 越权写项目会失败
- `main` 不获得项目路径
- provider 默认不泄露 workspace/shared/session root
- provider 通过 `AT_CONTEXT` 读取专属上下文契约
- `context.json` 只列出授权 shared 文件，不暴露 shared 目录
- 长期记忆更新只能被收集为 session proposal
- `code` 可进行最小项目写入
- `code` 写 shared 会失败
- `code` 写其他 agent 目录会失败
- `trace`、`audit`、`artifact`、`doctor` 可输出运行时证据

## 路线图

近期优先级：

- 增加 `run-step`、`audit`、`doctor` 等更细粒度 CLI 命令
- 增加 memory proposal 合并流程
- 增加 provider 能力探测
- 增加项目注册表和项目级测试命令
- 增加失败重试和回退到指定 agent
- 增加更硬的文件权限隔离

中期方向：

- Codex/opencode 真实 provider 模板
- 多 AT session 并发运行管理
- TUI 或对话框状态机视图
- agent 级日志、耗时、token 和成本统计
- shared memory/skills 的审核式更新

## 设计原则

- agent 负责产出内容，AT 负责流程控制
- 职责边界写入 `agent.md`
- 输出格式写入 `output.md`
- 写权限写入 `permissions.json`
- agent 之间只通过 handoff 通信
- shared 默认可读、不可随意写
- 长期记忆更新应走 proposal，而不是 agent 直接修改
- 最小权限优先，必要能力显式授予

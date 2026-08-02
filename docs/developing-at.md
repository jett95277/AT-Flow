# 开发 AT

本文档记录开发 AT Flow 时必须遵守的工程原则。它不是功能愿景，而是后续实现、重构和评审 AT runtime 时的判断标准。

## 核心判断

AT 壳子最重要的价值不是控制台外观，也不是简单把多个 agent 串起来，而是让多个强能力 CLI agent 在真实工程中可控协作。

因此优先级应当是：

1. 严格的 agent 职能边界
2. 明确的权限边界
3. 可治理的上下文与长短期记忆
4. 共享文档的受控访问与审核式更新
5. 可恢复、可观测、可测试的状态机 runtime
6. 最后才是 ASCII/TUI 展示层

界面可以帮助用户理解流程，但不能代替 runtime 契约。

## 职能分离

每个 agent 必须有独立的 `agent.md`，并且职责边界要写成硬约束，而不是建议。

`main`

只负责理解用户意图、任务范围、目标、非目标、验收标准和关键约束。默认不读大范围项目、不改代码、不运行测试、不做实现方案细节。

`analysis`

只负责项目理解、方案拆解、风险判断、执行计划和测试策略。默认可读项目，但不可修改项目文件，不应直接产出实现变更。

`code`

只负责按已确认的计划执行实现、修改项目文件、记录变更说明。默认是唯一拥有项目写权限的 agent，但不能直接修改 shared memory、skills、policies、session state 或其他 agent 目录。

`test`

只负责验证、测试执行、失败定位、证据记录和残余风险判断。默认可读项目，但不可修改生产代码。若发现问题，应输出 failure artifact 或回流建议，而不是越界修复。

## 物理隔离

职责边界必须配合物理隔离，否则 agent 很容易在上下文或文件层面互相污染。

每个 session 应拥有独立目录：

```text
.at/sessions/<session-id>/
```

每个 agent 应拥有独立目录：

```text
.at/sessions/<session-id>/agents/<agent>/
  agent.md
  permissions.json
  output.md
  input.json
  prompt.md
  inbox/
  outbox/
  workspace/
```

agent 不应直接读取其他 agent 的 workspace，也不应直接写入其他 agent 的 inbox/outbox。跨 agent 传递必须由 AT 脚本通过 handoff 完成。

## 上下文边界

上下文不能依赖模型自觉控制，应由 AT 显式生成。

每个 agent 执行前，AT 应生成该 agent 专属的 context contract：

```text
.at/sessions/<session-id>/context/<agent>.json
```

该文件只列出当前 agent 被允许知道和使用的内容，例如：

- 当前任务
- 当前阶段
- 被授权的 handoff artifact
- 被授权的 shared memory 文件
- 被授权的 skill 文件
- 被授权的项目路径
- 当前 agent 的权限文件和输出契约

默认不应暴露：

- workspace root
- shared root
- session root
- 其他 agent 的私有目录
- 未经授权的长期记忆文件

prompt 应从 context contract 构造，而不是让 provider 自由扫描整个 `.at` 目录。

## 记忆治理

AT 的记忆应分为短期记忆和长期记忆。

短期记忆属于 session：

```text
.at/sessions/<session-id>/context/
.at/sessions/<session-id>/handoff/
.at/sessions/<session-id>/agents/<agent>/inbox/
.at/sessions/<session-id>/agents/<agent>/outbox/
```

长期记忆属于 shared：

```text
.at/shared/memory/
  user.md
  project.md
  decisions.md
  rules.md
```

agent 默认只能读取被授权的长期记忆，不能直接修改长期记忆。任何长期记忆更新都必须写成 proposal：

```text
.at/sessions/<session-id>/memory-proposals/<agent>-*.md
```

是否合并 proposal 应由 AT 的审核流程决定，而不是由某个 agent 自行决定。

## 共享文档

shared 区域是跨 session 的公共知识层，但不能变成所有 agent 都能随意读写的公共硬盘。

建议结构：

```text
.at/shared/
  memory/
  skills/
  policies/
  docs/
  inbox/
```

访问原则：

- shared memory 默认受控读取，禁止直接写入
- shared skills 默认受控读取，禁止运行时随意改写
- shared policies 只能由维护者或审核流程修改
- shared docs 可作为项目知识库，但进入 prompt 前必须经过 context contract 选择
- shared inbox 只用于跨 session 输入，不应作为 agent 间通信通道

## Artifact 契约

agent 之间不共享可变对话上下文，只共享 artifact。

每一步的输出必须进入：

```text
.at/sessions/<session-id>/agents/<agent>/outbox/artifact.md
```

失败必须进入：

```text
.at/sessions/<session-id>/agents/<agent>/outbox/failure.json
```

artifact 应该结构化、可追踪、可被下一 agent 消费。AT 负责把 artifact 路由到 handoff 和下一个 agent 的 inbox。

## 脚本化关键节点

关键节点必须由 AT 脚本打通，不能交给 agent 自由发挥。

必要节点：

```text
prepare_agent
build_context
route_prior_handoff
run_agent
collect_output
collect_memory_proposals
audit_permissions
route_handoff
update_state
```

agent 只能在当前阶段产出内容，不能推进状态机、不能跳阶段、不能直接 retry、不能修改 session state。

## 可观测性

多 agent runtime 一旦不可观测，就很难维护。

至少必须保留：

- `trace.jsonl`：记录每个 runtime 节点、输入、输出、耗时和状态
- `artifact.md`：记录 agent 成功产物
- `failure.json`：记录失败类型、失败原因、是否可重试
- `audit/`：记录权限审计结果
- `memory-proposals/`：记录长期记忆变更请求

任何失败都应该能回答三个问题：

1. 哪个 agent 在哪个节点失败？
2. 输入和输出 artifact 是什么？
3. 失败是否可重试，为什么？

## 最小权限

默认策略应是拒绝，必要能力显式授予。

基础规则：

- `main` 默认无项目写权限
- `analysis` 默认只读项目
- `code` 默认可写项目
- `test` 默认只读项目
- 所有 agent 默认不能写 shared
- 所有 agent 默认不能写其他 agent 目录
- 所有 agent 默认不能写 session 控制文件
- provider 默认不继承完整父进程环境

如果某个 provider 或 agent 需要更高权限，必须能在 `permissions.json` 和 trace 中看见。

## 最小闭环验证

每次增强 AT runtime，都应优先补测试，而不是只跑通 happy path。

至少覆盖：

- 正常四 agent 流程
- 单步运行
- 失败任务
- retry
- 中断恢复
- 无 session
- 多 session 并存
- agent 越权写 shared
- agent 越权写其他 agent 目录
- code 最小项目写入
- context contract 不泄露根目录
- 长期记忆只能生成 proposal

## 开发优先级

当前阶段继续开发 AT 时，推荐顺序是：

1. 定义 context contract
2. 定义 memory contract
3. 强化 artifact contract
4. 完整 trace log
5. 失败恢复与 retry
6. 5-8 个端到端场景测试
7. 最后再增强 ASCII/TUI 展示

一句话原则：AT 要先成为可靠的 agent runtime，再成为好看的 agent 控制台。

## 一键配置脚本

V1.9 提供 `scripts/setup.py`（核心逻辑在 `src/at_flow/setup.py`）：

```powershell
python scripts/setup.py check     # 环境体检（只读）
python scripts/setup.py install   # 依赖 + 初始化 + 触发块 + 配置补全
python scripts/setup.py start     # 启动后端(:8000) 与前端(:3000)
python scripts/setup.py doctor    # 健康自检与就绪说明
```

脚本幂等；opencode 全局配置只补缺失键，at.config.json 只修复
codex/opencode 非交互命令，AGENTS.md 触发块通过既有
`install_codex_trigger` 追加/替换。

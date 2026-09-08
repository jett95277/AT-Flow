# orchestration/runtime Specification

## Purpose
定义 xiaot 的执行编排行为：经编排命令产出紧凑的执行指引，由**调用方 Coding Agent**（如当前 opencode 会话）执行任务并回报结果，使 xiaot 编排层与 Agent 会话解耦、Agent 适配可扩展，且失败与取消显式区分。

## Requirements

### Requirement: 编排命令以 Agent 注入形态提供

xiaot 编排命令 SHALL 以 Coding Agent 可发现的形态提供（如注入其 skills/commands 目录，Agent 会话启动即发现、按需触发）；Agent 在会话中接收到用户任务时 SHALL 可调用 xiaot 编排命令取得编排产物。

#### Scenario: Agent 会话发现并调用编排命令

- **WHEN** Agent（opencode）启动并加载了 xiaot 注入的编排命令
- **THEN** Agent 会话中可按指引调用 xiaot 编排命令
- **AND** 编排命令返回结构化编排产物

### Requirement: 执行由调用方 Agent 完成

xiaot SHALL 产出"可执行指引"（任务指令 + 记忆要点 + 技能/规范指引 + 路径引用）后交由**调用方 Agent**在当前会话执行；xiaot 编排层 MUST NOT 在 MVP 中自行拉起独立执行进程（headless 拉起为未来可选扩展，不构成当前行为要求）。

#### Scenario: 编排产物交当前会话 Agent 执行

- **WHEN** xiaot 编排完成并产出执行指引
- **THEN** 由调用方 Agent 按其执行
- **AND** xiaot 不启动独立 Agent 进程

### Requirement: 执行结果标准化回报

Agent 执行后 SHALL 以统一结果契约为 Agent 回报：状态显式区分成功、失败、取消与部分完成，携带任务标识、输出、产物清单与元数据；失败/取消 SHALL 显式表达，不得伪装成功。

#### Scenario: 失败/取消显式表达

- **WHEN** Agent 执行失败或被取消
- **THEN** 回报结果以对应失败/取消状态表达
- **AND** xiaot 不将其作为成功结果沉淀

### Requirement: 编排产物为引用式注入执行指引

xiaot 编排命令返回 SHALL 为"指令 + 摘要 + 路径引用"形态：规划产物完整持久化于 `.xiaot/` 工作区或规范工作区，注入对话的内联内容受预算限制，大块内容（记忆明细/规范全文）以路径引用、由 Agent 按需读取；xiaot MUST NOT 将记忆库或编排内部结构全文倾倒给 Agent。

#### Scenario: 大块内容按需引用

- **WHEN** 编排产物含大块记忆或规范内容
- **THEN** 内联仅含摘要与路径
- **AND** Agent 需要时读取所指文件而非接收全文

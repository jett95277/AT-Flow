## Purpose

定义 xiaot 的上下文编排行为：把任务、相关记忆摘要、选中技能与可选规范指引组装为**紧凑注入产物**（含路径引用），供 Agent 在当前会话执行时取用；xiaot 不接管 Agent 的会话上下文与压缩。

## ADDED Requirements

### Requirement: 产物完整 + 注入引用式

上下文编排 SHALL 将规划产物（plan/result/context 快照等）**完整持久化**不简化，并把任务指令、记忆摘要、技能要点与可选规范指引组装为**引用式注入产物**：注入对话的仅含指令块、每条一行摘要、少量约束与路径引用。

#### Scenario: 组装紧凑产物

- **WHEN** 规划产物就绪（任务/记忆/技能/规范可用）
- **THEN** 系统组装含指令块与引用的紧凑产物
- **AND** 该产物作为 Agent 执行的输入指引

### Requirement: 内联内容受预算限制

进入产物的内联内容 SHALL 受预算限制；超过预算的大块内容（记忆明细、规范全文、长文档）SHALL 以 `.xiaot/` 工作区或规范工作区中的路径引用呈现，由 Agent 按需读取，MUST NOT 全文内联。

#### Scenario: 超限内容转为引用

- **WHEN** 某内容超出内联预算
- **THEN** 产物只内联其摘要并附路径
- **AND** 不将全文直接放入产物

### Requirement: 记忆以注入摘要与引用形式进入

进入产物的记忆 SHALL 为已检索、已过滤条目的摘要（每条一行结论 + 来源 URI）；系统 MUST NOT 把记忆库本体、未过滤全量或内部结构暴露给 Agent。

#### Scenario: 记忆经摘要与 URI 注入

- **WHEN** Agent 需要记忆上下文
- **THEN** 仅收到相关条目的摘要与来源引用
- **AND** 拿不到记忆库内部结构

### Requirement: 与 Agent 会话上下文协作

xiaot 注入产物 SHALL 仅在任务启动/恢复时提供一次，作为短命任务指引；Agent 会话中的对话上下文、长会话压缩与 token 管理 SHALL 由 Agent 自身负责，xiaot 不干预、不接管。

#### Scenario: 注入不干预 Agent 压缩

- **WHEN** Agent 会话继续演变或触发压缩
- **THEN** xiaot 注入产物作为历史输入的一部分被 Agent 自行管理
- **AND** xiaot 不实现自己的会话压缩逻辑

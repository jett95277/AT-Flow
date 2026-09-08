# orchestration/skill Specification

## Purpose
定义 xiaot 的技能编排行为：以"编排动作 skill/command"形态注入 Coding Agent（项目级，Agent 启动发现、会话按需调用），并保留领域技能的双入口（编排路由 + 手动触发），让技能层成为编排 CLI 与 Agent 会话之间的驱动面。

## Requirements

### Requirement: 编排动作以 skill/command 注入项目级 Agent

xiaot 编排动作 SHALL 以 Coding Agent 可发现的 skill/command 形态注入项目级配置目录（如 `.opencode/`），Agent 启动即发现、会话中按需调用；注入 SHALL 为部署时写入 + 启动发现，非 Agent 运行期动态注入。

#### Scenario: 项目内 Agent 发现编排命令

- **WHEN** 项目已注入 xiaot 编排 skill/command 且 Agent 启动
- **THEN** Agent 会话中可发现并按需调用编排命令
- **AND** 编排命令调用 xiaot CLI 引擎

### Requirement: core 编排命令集

xiaot SHALL 提供核心编排命令集：`task`（启动/恢复任务闭环）、`retrieve`（注入任务相关记忆）、`plan`（产出并落盘规划指引）、`context`（组装上下文片段）、`settle`（收工沉淀建议）；命令返回 SHALL 为机器可读 JSON（含指令/摘要/路径引用）。

#### Scenario: 五个核心命令覆盖主循环

- **WHEN** Agent 按编排流程推进任务
- **THEN** 依序可用 task/retrieve/plan/context/settle 命令
- **AND** 各命令返回机器可读结果

### Requirement: 领域技能双入口

领域技能（记忆操作/报告/简化等既有技能）SHALL 保留两个入口：被编排层按任务路由（指引中携带技能要点）；及 Agent 会话中按触发词手动调用。编排路由与手动触发互不排斥。

#### Scenario: 技能可编排亦可手动

- **WHEN** 任务与某领域技能相关
- **THEN** 编排在指引中携带该技能要点
- **WHEN** 用户直接表达技能触发意图
- **THEN** Agent 亦可直接按技能执行

### Requirement: 技能是工作流驱动而非执行器

编排与领域技能 SHALL 作为"何时调用 CLI、按什么流程走"的指令指引；真正的执行能力在 xiaot CLI（编排）与 Agent（执行）与既有引擎，技能 MUST NOT 被当作可执行 API。

#### Scenario: 技能驱动而非代执行

- **WHEN** Agent 遵循技能指引
- **THEN** 技能文本指导其调用对应 CLI/流程
- **AND** 技能本身不直接产生系统执行能力

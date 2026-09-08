## Why

xiaot 当前（v3.1）是"Skill 工具集 + 记忆脚本"：13 个技能靠人用触发词手动调用，记忆引擎（xiaot_memory）能写会治理但没有"按任务取用"，缺少**任务编排核心**。用户给一句话任务时，系统没有"先规划、再注入 Coding Agent 执行、再把结果沉淀回记忆"的主循环——规划靠 Agent 自觉，产物不落盘、不可审计，跨会话记忆不连续。

对标 spec-driven 的"先规划后注入执行"设计理念，本次把 xiaot 升级为**面向 Coding Agent 的轻量级任务编排层（Orchestrator / Harness 雏形）**：任务先经编排层结构化规划（复用记忆/技能/规范能力），规划完备后才注入 Coding Agent 执行，执行结果经治理沉淀回三层记忆。

为什么现在：记忆引擎（治理/检索/结算）已成熟，技能体系已齐，但缺"把它们组织成一个任务执行生命周期"的一层——这正是本次要补的核心。

## What Changes

xiaot v3.0 新增**任务编排引擎**（CLI + 编排命令，部署为可移植命令入口），并以 skill/command 形式**注入 Coding Agent**（以 opencode 为例，写入其 skills/commands 目录，Agent 启动即发现、会话中按需调用），把记忆/技能/规范编排能力接入 Coding Agent 会话：

- 新增 `xiaot` CLI（编排引擎）：任务分析、记忆检索注入、技能路由、规范判定、产物落盘、结果沉淀等编排命令。
- 新增编排命令 skills 注入 opencode（`.opencode/`）：Agent 会话中用户自然语言 → Agent 按 xiaot 指引调用 xiaot CLI 编排 → 取得编排产物。
- 编排产物为**紧凑 ContextPack**（指令块 + 记忆摘要 + 技能/规范要点 + 路径引用）：内联内容有上限，超出部分按需引用 `.xiaot/` 工作区与规范工作区文件——与 Agent 自身会话上下文协作，xiaot 不干预 Agent 的上下文压缩。
- 执行由**调用方 Agent（当前 opencode 会话）完成**：xiaot 产出"可执行指引"（含 Plan、记忆要点、spec 路径）后，Agent 按其执行；xiaot 不拉起独立执行进程（headless 拉起为未来可选扩展，MVP 不做）。
- 规范分支（Spec 编排）复用开源 spec-driven 工作流（CLI + 工作区），xiaot 只做判定与驱动。
- Plan 产物落盘（项目 `.xiaot/workspace/<task-id>/`：plan/result/context 快照），状态由产物与 Result 推导。

不改变：xiaot_memory 记忆引擎（薄封装复用）、13 个技能、记忆命令 CLI、规则/人设层。

## Capabilities

### New Capabilities
- `orchestration/task-lifecycle`: 任务编排主循环——Task 建模、规划→注入→执行→沉淀生命周期、状态推导、边界处理（记忆空/技能空/失败）。
- `orchestration/memory`: 记忆编排——按任务检索过滤并注入（复用现有记忆引擎的上下文构建与治理）、结果经治理沉淀回三层。
- `orchestration/skill`: 技能编排——自动发现与路由技能（扫 skills/ 目录匹配），无匹配不阻塞。
- `orchestration/spec`: 规范编排——判定任务是否需要规范工作流，驱动开源 spec-driven 流程产出规划产物，失败返回明确错误。
- `orchestration/context`: 上下文编排——把任务/记忆/技能/规范组装成统一 ContextPack（注入契约），含大小限制。
- `orchestration/runtime`: 执行编排——RuntimeAdapter 抽象、Coding Agent 适配、Result 标准化（success/failed/cancelled/partial）。

### Modified Capabilities
<!-- 无：v3.0 全部为新增能力，不修改既有 spec -->

## Impact

- 新增代码：`lib/python/xiaot/` 编排包（编排命令实现：memory/skill/spec 编排 + context 构建 + 规划产物）+ 仓库级 `xiaot` CLI 薄壳 + **注入 opencode 的编排 skills/commands 生成器**。
- 执行模型：xiaot 编排产出紧凑 ContextPack 交给**调用方 Agent**（当前 opencode 会话）执行；xiaot 不拉起独立执行进程。
- 复用：xiaot_memory 记忆引擎（memory_context/memory_policy/memory_settle）、13 个技能、现有 .ps1 工具。
- 产物目录：`.xiaot/workspace/<task-id>/`（plan/result/context 快照，可审计）；`xiaot` 编排命令以 skills 注入 opencode（`.opencode/`）。
- 规范工作区：复用开源 spec-driven 工具的工作区约定。
- 依赖：Python（编排包，复用 PyYAML）；执行经调用方 Agent；规范经外部 spec-driven CLI。
- 测试：新增单元/集成/E2E；现有 83 单测不回归。
- 边界：不重造 Coding Agent/规范引擎；不拉起 headless 执行（可选扩展）；不做 Web UI/多用户/分布式记忆。

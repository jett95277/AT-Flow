## Context

xiaot v3.1 已有：自研三层记忆引擎（`xiaot_memory`：memory_context 检索注入 / memory_policy 治理准入 / memory_settle 结算）、13 个技能（人触发 SOP）、记忆命令 CLI、可移植 PS 工具。现状缺任务编排核心，规划靠 Agent 自觉、产物不落盘。

v3.0 新增编排层，设计基线见 `xiaot/ARCHITECTURE-v3.md`（含 G1-G7 核验与 O1-O6 收敛）。本 design 落地该基线：新包 `lib/python/xiaot/`（与 xiaot_memory 并列），复用最大化，不重造既有引擎与规范引擎。

## Goals / Non-Goals

**Goals:**
- 提供 `Orchestrator.run(task)` 主循环：规划 → 注入 → 执行 → 沉淀，Plan 就绪前不调执行层
- 任务入口 CLI（`xiaot "<任务>"`），只做入口与结果输出
- 记忆编排薄封装现有引擎（检索过滤 + 结果治理沉淀），零重写
- 技能编排自动发现/路由现有 13 个技能
- 规范编排：判定 + 驱动开源 spec-driven 工作流（CLI + 工作区），失败明确报错
- ContextPack 统一注入契约 + 大小限制
- RuntimeAdapter 抽象 + Mock 先行，Agent 适配后接 opencode
- Result 四状态标准化 + 结果经治理沉淀
- Plan 产物落盘（`.xiaot/workspace/<task-id>/`），状态从产物与结果推导

**Non-Goals:**
- 不重造 Coding Agent / Agent Loop / Tool Calling / 模型推理
- 不重造规范引擎（DSL/产物模型/状态机/校验）
- 不做 Web UI / 多用户 / 分布式记忆 / 自造上下文压缩
- 不迁移重构现有 `xiaot_memory` 引擎内部（仅新增封装层）

## Decisions

1. **新包位置与命名**：`lib/python/xiaot/`（编排包，与 `xiaot_memory` 并列）。编排能力以**命令集**暴露（`xiaot <sub>`：编排命令），并生成注入 opencode 的 skills/commands（`.opencode/`），Agent 启动发现、会话内按需调用。仓库根 `bin/xiaot.ps1` 薄壳。
   *备选*：并入 xiaot_memory（拒：污染成熟引擎）；xiaot CLI 只做"任务入口+拉 headless"（拒：与"Agent 内嵌编排"真实架构不符）。

2. **记忆编排薄封装**（复用最大化）：`memory_service.py` 只做两件事——
   - `retrieve(task)`：把 Task 的归属/项目映射为检索参数 → 调现有 `memory_context.build_memory_context`（含 filter_entries/scope 优先级/is_injectable）+ budget 裁剪 → 返回 `MemoryContext`
   - `process_result(task,result)`：结果分类 → 走现有 `memory_policy` 准入写 short candidate（绑 task）→ 结算/提升仍走 `memory_settle` 与人工确认
   新代码不含记忆存储逻辑。

3. **Plan 产物落盘**：`.xiaot/workspace/<task-id>/{plan.md,result.md,context.json}`。plan.md = 目标/步骤(≤10)/期望产物/验收（模板），无独立状态文件（状态由产物存在 + Result 推导）。context.json 存 ContextPack 快照（可审计/重放）。与 `.agent/memory/`（沉淀真相）隔离：workspace=在途，memory=已确立。

4. **三把关点**：闸 1 Plan 产出后展示待确认；闸 2 记忆 promote 人工确认（沿用）；闸 3 结果关键沉淀确认（轻量=用户点头，规范=按验收+终确认）。规划边界：规划层不写业务码、不调执行层。

5. **技能编排**：`skill_router.resolve(task)` 扫技能目录读取各 `SKILL.md` 的 description，关键词/意图匹配 → `[SkillContext]`（可空→基础路径）。技能本身不执行（指引入 ContextPack）。

6. **规范编排**（复用开源 spec-driven）：`spec_router.resolve(task)` 判定（信号：任务意图含"实现/新增 X/系统级"或影响面超阈值，规则存 config）；判需规范 → `spec_adapter` 调开源 spec-driven CLI 的机器面（`--json`）建工作单元/读状态/取指令 → 规范产物路径收进 ContextPack.spec；规范流程不可用/失败 → 明确错误（不静默退化）。普通任务不走规范。

7. **执行编排（调用方 Agent 执行）**：xiaot 编排命令产出**执行指引（产物完整落盘 + 注入引用式）**——规划产物完整持久化于 `.xiaot/workspace/<task-id>/` 与规范工作区；注入给调用方 Agent 的是"指令 + 摘要 + 路径引用"，Agent 按需读取完整文件（对齐 spec-driven instructions 模式）。MVP 用可验证的"指引格式 + Mock 回报"先行；xiaot 不拉起独立进程（headless 为可选扩展）。

8. **产物完整 + 注入引用式**：规划产物（plan/result/context 快照、规范文档）完整落盘不简化；注入对话的只有指令 + 每条一行摘要 + `.xiaot/`/规范工作区路径引用。xiaot 只在任务启动/恢复注入一次，不干预 Agent 会话压缩。

9. **结果沉淀分类器（轻量）**：信号 = 是否带证据/用户确认/任务类型；默认只写 short candidate（绑 task），升层须治理+人工。失败/取消结果不进入记忆（记 workspace + 事件）。

10. **CLI 形态与边界**：xiaot CLI 是**编排命令集**（analyze/plan/retrieve/settle 等编排子命令 + 注入 opencode 的 skills 生成）；编排命令只产出编排产物，不碰执行细节（执行由调用方 Agent 完成）；`bin/xiaot.ps1` 薄壳。

11. **错误与边界**：记忆空/异常、技能空 → 警告降级继续；执行失败 → failed Result；规范失败（判需时）→ 明确错误。

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| opencode 回报形态未验证 | MVP 用"紧凑指引格式 + Mock 回报"先行走通编排；真实 Agent 回报待会话内实测，格式契约不变 |
| 规范判定阈值不准 | 规则可配，默认保守（普通任务不走规范） |
| 编排层与记忆引擎耦合 | 只经 MemoryService 接口 + 数据契约，禁直连 store |
| 复用层行为假设错误 | 每个封装加针对现有引擎行为的契约测试，83 旧测回归 |
| 任务编排产物与规范工作区双轨 | workspace 存轻量 Plan 与 Result；规范任务产物在规范工作区，xiaot 只存路径与决策 |
| 演进（Harness） | 三接口 + ContextPack/Result 契约即扩展点；编排前后留 hook 位 |

# xiaot v3.0 架构设计（MVP 定稿基线 · 2026-09-08）

> 状态：**MVP 基线已收敛**（经核验 G1-G7 补强 + O1-O6 决策）；据此进入 MVP 构建，定稿前大改动须回本文档。
> 构建原则：**能复用现有内容优先复用**；能复用 spec-driven 架构设计就复用。

---

## 0. 一句话

xiaot v3.0 从一个"Skill 工具集 + 记忆脚本"升级为**面向 Coding Agent 的轻量级任务编排层**，核心设计理念对标 **spec-driven 规划先行**：先结构化规划，规划完备后才注入 Coding Agent 执行。

## 1. 背景与动机

### 现状（v3.1）
- 13 个 Skill（人设 / SOP / 报告 / 简化 / prompt 优化）
- 自研三层记忆引擎（xiaot_memory：add/verify/settle/promote 治理，83 单测）
- 记忆命令 CLI（xiaot-memory）

### 差距
- 没有**任务主循环**：接收用户一句话任务后，缺少"分析 → 编排 → 规划 → 注入执行 → 结果沉淀"的编排核心
- 记忆只会"写"，不会按任务"检索注入"
- Skill 靠人手动触发，无自动路由
- 一句话任务直接丢给 Coding Agent 自己摸索，规划靠 Agent 自觉，产物不落盘、不可审计

### 目标
```
User 一句话任务
  → xiaot 编排层：分析 → 记忆检索 → 技能路由 → 规范判定
  → 产出规划产物（落盘）
  → 注入 Coding Agent 执行
  → 结果沉淀回记忆
```

## 2. 设计理念（对标 spec-driven 规划先行）

| 理念 | 含义 | xiaot 对应 |
|---|---|---|
| **先规划后执行** | 规划阶段不写代码，规划完备才进入实现 | Orchestrator 规划层先产出 Plan，**Plan 就绪前不注入执行** |
| **产物落盘、状态推导** | 状态不写在文件里，由产物存在/完成度推导 | Task 状态 = Plan 产物完整度 + Result；不维护冗余状态 |
| **真相 vs 提案** | 提案（在途）与真相（已确立）分离，归档时合并 | 在途 Task+Plan（提案）→ 结果经治理并入记忆（真相） |
| **Actions, not phases** | 无死阶段门；依赖是使能条件而非关卡 | 规划各步可按需：记忆可空、技能可空、规范可选 |
| **引擎 / 方向盘 / 把关** | 引擎算状态给指令；Agent 做决策；人把关关键点 | xiaot CLI/Orchestrator=引擎；Coding Agent=方向盘；人在关键确认点把关 |
| **聚焦工作单元** | 一次一个聚焦单元（change） | 一次一个 Task（task-`<NNN>-<id>`） |
| **机器可读契约** | CLI 全命令 JSON 化 | ContextPack / Result 为结构化契约 |
| **渐进式严谨** | 轻量起步，按需加严 | 轻量任务即时规划；规范任务走完整规范工作流 |
| **治理与验证** | 合并前校验、结果审计 | 记忆治理（verify/settle）+ Result 校验 |

## 3. 目标架构（三层）

```text
┌──────────────────────────────────────────────────┐
│ ① 规划层（xiaot Orchestrator）                    │
│    Task → 分析 → 记忆检索 → 技能路由 → 规范判定     │
│    → 产出【Plan 产物】                            │
│                                                  │
│    Plan 产物（落盘，两套深度）：                    │
│      A. 轻量任务 → task-<id>/plan/ 目录            │
│         （plan.md：任务分解 + 期望产物）            │
│      B. 规范任务 → 规范工作区                       │
│         （proposal / specs / tasks，复用 spec-     │
│           driven 工作流）                          │
└───────────────────┬──────────────────────────────┘
                    │ Plan 就绪
                    ▼
┌──────────────────────────────────────────────────┐
│ ② 注入层                                          │
│    ContextPack（统一注入契约）                     │
│    { Task, Memory(相关), Skills(选中),             │
│      Spec(指引|None), Constraints, Metadata }     │
└───────────────────┬──────────────────────────────┘
                    ▼
┌──────────────────────────────────────────────────┐
│ ③ 执行层                                          │
│    RuntimeAdapter → Coding Agent（执行）          │
│    → Result{status, output, artifacts, metadata}  │
└───────────────────┬──────────────────────────────┘
                    ▼
         结果沉淀：Result → 分析 → 记忆治理 → 三层
```

## 4. 规划层设计

### 4.1 规划流程（对标 propose 阶段禁写代码）
```
Task（用户一句话）
  ├→ MemoryService.retrieve(task)    相关记忆（过滤+预算）
  ├→ SkillRouter.resolve(task)       选中技能（怎么干），可空
  ├→ SpecRouter.resolve(task)        是否需规范流程，可空
  └→ 规划产物生成器
       轻量：PlanPack（plan.md 落盘 task-<id>/plan/）
       规范：规范工作区（proposal → specs → tasks）
```
**约束**：规划层不调 Coding Agent 执行、不写业务代码；产物未成禁止进入注入层。

### 4.2 Plan 产物（落盘，对标 changes/ 模式）
```
task-<NNN>-<id>/                     # 轻量任务规划（对标 一个工作单元一个目录）
└── plan/
    ├── plan.md                      # 任务分解：目标/步骤/期望产物/验收
    └── status.json?                 # （设计决策：是否要状态文件——待定，倾向产物推导）
```
规范任务的产物进**规范工作区**（由 spec-driven 工作流管理，xiaot 只做路由与注入）。

### 4.3 Spec 判定（对标渐进式严谨）
| 信号 | 判定 |
|---|---|
| 涉及 >N 文件 / 新功能 / 用户明示"实现一个 XX" | 走规范工作流 |
| 普通修改 / 问答 / 轻量任务 | 轻量 PlanPack |
| 判定规则可配置 | config 可调 |

## 5. 注入层（ContextPack 契约）

```
@dataclass ContextPack:
    task: Task
    memory: MemoryContext          # 仅相关条目（已检索+裁剪）
    skills: list[SkillContext]     # 选中技能指引（可空）
    spec: SpecContext | None       # 规范指引（规范任务才有）
    constraints: list[str]
    metadata: dict                 # trace id / 项目 / session 等
```

ContextPack 是 xiaot 与 Coding Agent 之间**唯一数据契约**：
- 相关记忆以"上下文"进入，绝不暴露记忆库
- 技能以"行为指引"注入，不等同 Agent API
- 规范任务带 spec 产物路径与流程状态

## 6. 执行层（Runtime）

```
RuntimeAdapter(Protocol)
  execute(context: ContextPack) -> Result

OpenCodeAdapter  # 具体实现：把 ContextPack 转为 Coding Agent 可执行输入
  - 普通任务：构造执行 prompt（含 plan/记忆/技能指引）→ 调 CLI
  - 规范任务：让 Agent 按 tasks.md 实现（走 apply 语义）
```

Result：
```
@dataclass Result:
    task_id: str
    status: success | failed | cancelled | partial
    output: str
    artifacts: list[str]
    metadata: dict
```

## 7. 结果沉淀（对标治理验证）

```
Result → 分析 → 分类（临时/项目事实/稳定知识/模型生成）
  → 治理准入（走现有记忆引擎 add/verify/settle）
  → 验证过的 → medium；稳定跨项目 → long；临时 → 过期/清理
```
**失败/取消的 Result 不作为成功知识进入长期记忆。**

## 8. 状态与生命周期

- Task 状态由产物推导：Plan 产物缺失=规划中；Plan 完整+未执行=待注入；Result 成功=完成
- 不引入独立状态机（除非发现必要）

## 9. 模块落点（现有基础上更新）

```text
lib/python/
├── xiaot_memory/       # 现有记忆引擎（保留零改动，封装后使用）
└── xiaot_orch/         # 新增编排包（本次全部新代码）
    ├── models.py           # Task/Result/ContextPack/各 Context
    ├── plan_store.py       # Plan 产物落盘（task-<id>/plan/）
    ├── memory_service.py   # 封装记忆引擎 → retrieve/process_result
    ├── skill_router.py     # 扫描 skills/ + 匹配
    ├── spec_router.py      # 规范判定
    ├── spec_adapter.py     # 规范工作流驱动（内部复用开源 spec CLI）
    ├── context_builder.py  # ContextPack 组装
    ├── runtime.py          # RuntimeAdapter + OpenCodeAdapter
    ├── result_processor.py # Result → 治理
    ├── orchestrator.py     # 主循环
    └── cli_main.py         # xiaot "<task>" 入口
```

## 10. 与现状关系

| 现状 | 处置 |
|---|---|
| `xiaot_memory` 引擎 + 治理 | 保留，经 `memory_service` 封装接入 |
| `skills/` 13 个 Skill | 保留，SkillRouter 自动发现 |
| 记忆命令 CLI | 保留（xiaot-memory），新增任务 CLI（xiaot） |
| AGENTS/routing/doctor/tui | 保留 |

## 11. 边界（明确不做，对标 MVP）

- 不重新实现 Coding Agent / Agent Loop / Tool Calling
- 不重新实现 spec 引擎（DSL/artifact/状态机）——复用开源 spec-driven 工作流
- 不做 Web UI / 多用户 / 分布式记忆
- 不自造 Context 压缩（跨 Session 记忆由 xiaot 管）

## 12. 核验补强（G1-G7，2026-09-08 定稿）

### G1 记忆服务复用（不重写）
`memory_service.retrieve` = **薄封装现有 `xiaot_memory.memory_context`**：
- `build_memory_context` / `filter_entries` / `resolve_scope_precedence`（检索注入雏形已在引擎）
- 治理写入走 `memory_policy`（check_admission/request_verify/request_promote）
- 结算走 `memory_settle`（settle_task/classify_entries）
- **新增仅**：Task→查询参数映射 + budget 裁剪封装

### G2 Plan 产物落盘位置（收敛）
```
项目根 .xiaot/workspace/<task-id>/
├── plan.md        # 目标/步骤/期望产物/验收（轻量任务）
├── result.md      # Result 摘要 + 沉淀结论
└── context.json   # ContextPack 快照（可审计/可重放）
```
与 `.agent/memory/`（记忆库）**隔离**：workspace 是"在途工作"，memory 是"沉淀真相"。

### G3 人把关点（三闸，对标"人把关"）
| 闸 | 位置 | 动作 |
|---|---|---|
| 闸 1 | Plan 产出后 | 展示 Plan → 人确认 → 才注入执行 |
| 闸 2 | promote 记忆 | 沿用现有：人工确认后 promote |
| 闸 3 | Result 关键沉淀 | 轻量=用户确认；规范=按验收 + 用户终确认 |

### G4 Result → 记忆分类器（轻量判定）
- 信号：带 `evidence` / 用户确认 / 任务类型（dev 类重验证，报告类轻）
- 默认动作：Result 只写 **short candidate**（绑 task）→ 人工 settle/verify 后才可能升层
- **失败/取消 Result 不进入记忆**（仅记 workspace result.md + 事件）

### G5 CLI 职责边界
`cli_main` 只做：解析任务 → 建 Task → `Orchestrator.run` → 输出 Result。
**不碰**：Memory/Skill/Spec 查询、OpenCode 调用细节、记忆写入（全在 Orchestrator 内部）。

### G6 测试矩阵（映射闭环）
| 层 | 覆盖 |
|---|---|
| unit | models / memory_service（复用封装）/ skill_router 3 态 / spec_router / context_builder / runtime 4 态 / result 分类 |
| integration | CLI→Orchestrator（Memory/Skill/Context/Runtime(Mock)） |
| E2E | 普通任务链 / spec 任务链 / 记忆生命周期链 |
| 回归 | 现有 83 单测不回归 |

### G7 验收映射（任务书十问 → 架构节）
| 问 | 答案在 |
|---|---|
| 小T 是什么 | §0（编排层） |
| opencode 是什么 | §6（执行 Runtime） |
| Memory 是什么 | §7+§8（跨会话知识，xiaot 管生命周期） |
| Skill 是什么 | §4 技能路由（行为指引） |
| Spec 是什么 | §4.3 规范判定（可选分支） |
| spec 工具是什么 | §6（复用的实现） |
| 如何调 opencode | §6 ContextPack→Adapter |
| Memory 如何进 opencode | §5 检索→ContextPack 注入（不裸暴露） |
| 执行完怎么办 | §7 Result→提取→治理 |
| 如何演进 Harness | §11 边界 + 扩展点 |

## 13. 开放问题收敛决策（O1-O6）
| 开放问题 | 决策 |
|---|---|
| O1 plan.md 格式/状态文件 | 无状态文件（状态从产物+Result 推导）；plan.md = 目标/步骤/期望产物/验收 |
| O2 轻量 Plan 最小粒度 | 目标句 + 步骤列表(≤10) + 期望产物 + 验收句，≤1 屏 |
| O3 spec 判定初值 | 硬编码信号：含"实现/新增 X 功能/系统级"或涉 >3 文件 → 规范流；规则存 config 可调 |
| O4 规范工作区与记忆关联 | 规范产物路径写回 workspace/result.md；记忆只存决策/结论，不存 spec 全文 |
| O5 opencode 调用形态 | MVP 先 MockAdapter 走通编排；OpenCodeAdapter 用非交互 CLI（session run），真接待实测 |
| O6 结果验证 | 轻量=用户确认；规范=按 tasks 验收+终确认 |

## 14. MVP 构建复用最大化映射
| MVP 模块 | 复用来源 | 新增量 |
|---|---|---|
| models | memory_models（枚举可继承扩展） | Task/Result/ContextPack 数据类 |
| memory_service | memory_context + memory_policy + memory_settle | 薄封装层 |
| skill_router | skills/（13 个，扫 description） | 匹配逻辑 |
| spec 分支 | spec-driven 工作流（本机 CLI 已装 1.12.0） | spec_router 判定 + adapter |
| runtime | — | RuntimeAdapter(Mock 先行) |
| result_processor | memory_policy/settle | 分类器 |
| orchestrator | — | 主循环 |
| cli_main | bin/ 薄壳模式 | 入口 |

---

*本文档为 MVP 基线；实现阶段每模块先在此对齐再编码。*

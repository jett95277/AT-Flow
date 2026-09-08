# 小T（Xiaot）

**Codex / OpenCode 通用的个人 AI 助手系统（v3.1 自包含：记忆引擎内迁 + 任务编排层）。**
>claude没顺手改是因为目前在家里用codex比较多，在公司用opencode，后期顺手加上claude，或者说使用者稍微写一段prompt就能适配

小T不是产品，不做面向用户的多余内容。系统要能跑、
行为可解释、边界清楚、结果可验证。

## 定位

小T 是个人开发流程里的人设与 SOP 层：定义"怎么说话、怎么记、怎么恢复"。
v3.1 起小T **完全独立**：三层记忆引擎已内迁为 `xiaot_memory` 模块，
基于 Codex / OpenCode 通用机制
实现（AGENTS.md + SKILL.md + 薄记忆命令），同一套文件双生态可用。

v3.0 起小T 在记忆层之上新增**任务编排层**（`lib/python/xiaot/` 编排 CLI，对齐
spec-driven 设计）：注入 Coding Agent（opencode 等），开发任务先经
`xiaot task` 编排（带记忆开工）→ 执行 → `xiaot settle`/`confirm`（留记忆
收工，全人工确认），使小T 从"人设/记忆工具"升级为"agent 上层任务编排平台"。
（详见下方「任务编排 CLI」节与 `ARCHITECTURE-v3.md`）

核心问题只有一个：
> 让人（和 Agent）清楚地看到当前记住了什么，并能随时查看、写入、提升、回滚。

---------------------------------------------------------------------------------------------------------------------
手打：小T本身是我的AT多智能体协作项目的副产品，但是由于AT项目多智能体编排效果不理想，目前v2.0之前都不专门进行维护，因为发现ORCA和MULTICA还有Agent Orchestrater这类多智能体编排平台已经非常完善，自己目前也在使用multica，再开发AT反而更像是玩具，本身项目的需求就是辅助个人开发工具，所以使用成熟的编排器更划算。
小T在目前使用个人体验不错，虽然只是skill的组合和长中短三层记忆的规则处理，但是交互的体验确实能够提升使用时的感受（或许是情绪价值）。
目前的使用路线是
小T->coding agent(codex/opencode/...)->skills/mcp->项目
小T->multica->coding agent->skills/mcp->项目

小T是一个上层的交互端组件，支持

| 你说 | 触发 | 作用 |
|---|---|---|
| 记一下 / 记录 / 保存 | xiaot-memo | 一句话沉淀三字段到 AT 记忆 |
| 继续 <任务> / 切换 <任务> | xiaot-continue | 恢复任务目标/约束/未决 + 时间线 |
| 创建 <专题> / 新任务 | xiaot-topic | 定义任务级记忆 |
| 打点 / 存个档 | at-memory-checkpoint | 打生命线节点 |
等等...非常目前共计12条规则，用户可以自定义，小T进步空间很大，因为目前就是起点

并且小T可以支持三种人设，目前每种人设的默认比较简单，个人开发时进行自定义调整，还是那句话：情绪价值拉满：）
----------------------------------------------------------------------------------------------------------------------
## 结构

| 层 | 落地 | 说明 |
|---|---|---|
| 规则层 | `AGENTS.md` | 12 条规则 + 权限管理 + Git 工作流 |
| 定位层 | `lib/xiaot-env.ps1` + `bin/xiaot-memory.ps1` | 统一解析 XIAOT_HOME / ProjectRoot / python / 记忆命令 |
| 记忆层 | `lib/python/xiaot_memory/` | 内迁记忆引擎（三层记忆 + 治理层，复用 AT 语义） |
| 编排层 | `lib/python/xiaot/`（v3.1 分层） | 任务编排 CLI：task/retrieve/plan/settle/confirm/checkpoint/timeline/rollback/init/inject（对齐 spec-driven） |
| 人设层 | `personas/*.md` | 全局/研发/产品三模式（charter 化） |
| SOP 层 | `skills/`（13 个 skill） | 自有 7 个 + 现成引入 6 个 |
| 路由层 | `routing.md` | 触发词→skill 路由 + 降级规则 |
| 模板层 | `templates/task-template.md` | 专题结构模板（序号化 + 目标/范围/验收） |
| 会话层 | `xiaot-memory memory checkpoint` | 记忆层生命线 |
| 启动层 | `xiaot-continue` skill | 按需恢复，不自动注入 |
                 用户任务（在 agent 会话里）
                        │
                        ▼
        ┌───────────────────────────────────┐
        │     xiaot 编排层（Orchestrator）      │
        │  理解任务 → 调度 → 组装 → 收口        │
        └──┬──────────┬──────────┬──────────┘
           │          │          │
       【同级】    【同级】     【同级】
           ▼          ▼          ▼
   ┌────────────┐ ┌──────────┐ ┌────────────┐
   │ 记忆能力     │ │ 技能能力  │ │ 规范能力     │
   │ Memory      │ │ Skill     │ │ Spec        │
   │            │ │          │ │            │
   │ xiaot_memory│ │ skills/13 │ │ 复用 spec-  │
   │ 三层(验证结论)│ │ 指引路由   │ │ driven 工作流│
   │            │ │          │ │            │
   │ A模型/治理   │ │ 双入口    │ │ 大任务分支   │
   └──────┬─────┘ └────┬─────┘ └──────┬─────┘
          │           │              │
          └───────────┴──────┬───────┘
                             │  编排层汇聚三者产物
                             ▼
              ┌─────────────────────────────┐
              │ Context 组装（ContextPack）    │
              │ 指令 + 记忆摘要 + 技能要点 +   │
              │ spec 路径（引用式、预算受限）    │
              └──────────────┬──────────────┘
                             ▼
                注入 Coding Agent（当前会话）
                             │ 执行
                             ▼
                        Result
                             │
                             ▼
             编排层收口：settle(建议) → confirm(人工)
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
          记忆(medium/long) 工作区(产物)   时间线(节点)

## 目录结构

```text
xiaot/
├── AGENTS.md               # 规则层（Codex / OpenCode 通用）
├── routing.md              # 路由层：触发词→skill 表 + 降级规则
├── ARCHITECTURE-v3.md      # 架构设计（v3.0 编排平台基线）
├── DEPLOY.md               # 部署文档（独立仓库 clone 即用）
├── sync-skills.ps1         # 一键同步 skills + 部署 ~/.xiaot 安装根
├── tui.ps1                 # 状态面板（交互 + text 双模式）
├── doctor.ps1              # 路径诊断（python + 记忆自检 + skills 部署）
├── openspec/               # spec-driven 工作区（specs=真相对外文档；changes/archive=演进历史）
├── tests/                  # 155 单测（记忆引擎 + 编排层）
├── lib/
│   ├── xiaot-env.ps1       # 定位层：导出 $Xiaot（MemoryCmd / PythonExe / ProjectRoot）
│   └── python/
│       ├── xiaot_memory/   # 记忆引擎（内迁：memory/policy/settle/context/events/timeline/view）
│       └── xiaot/          # 编排层：models/ports/orchestrator/workspace/memory_service/
│                           #   skill_router/spec_router/spec_adapter/commands/timeline/inject/cli
├── bin/
│   ├── xiaot-memory.ps1    # 薄记忆命令入口（python -m xiaot_memory）
│   ├── xiaot.ps1 / xiaot.cmd  # 编排 CLI 入口（python -m xiaot，PATH 可调）
│   └── setup-xiaot.ps1     # 一键部署（加入 PATH + 自检）
├── docs/
│   └── TASKBOOK-v3.0-orchestrator.md  # 编排平台开发任务书
├── personas/               # 人设层（charter 化）
│   ├── persona_global.md   # 全局人设
│   ├── persona_dev.md      # 研发人设
│   └── persona_pm.md       # 产品人设
├── templates/
│   └── task-template.md    # 专题结构模板
├── skills/                 # SOP 层（SKILL.md 格式）
│   ├── xiaot-memo/         # 一句话记录（自有）
│   ├── xiaot-continue/     # 恢复任务上下文（自有）
│   ├── xiaot-topic/        # 创建任务定义（自有，序号化）
│   ├── xiaot-workflow/     # 计划-执行-记忆沉淀全流程（自有，S/M/L 分级）
│   ├── at-memory-checkpoint/ # 生命线打点（自有）
│   ├── xiaot-status/       # 状态面板 TUI 入口（自有）
│   ├── xiaot-memory-manage/  # 三层记忆整理（自有）
│   ├── doc-coauthoring/    # 文档协作：PRD/技术方案/RFC（Anthropic 官方）
│   ├── web-artifacts-builder/ # HTML 报告/artifact（Anthropic 官方）
│   ├── mckinsey-consultant/  # 顾问式报告/竞品/PPT（社区 fleurytian，MIT）
│   ├── mimeng-writing/     # 中文爆款写作（社区 fleurytian，MIT）
│   ├── code-simplification/  # 代码简化（社区 addyosmani，MIT）
│   └── directional-prompting/ # prompt 优化（社区 kingbootoshi，MIT）
└── README.md
```

## 使用方式

### 部署（独立仓库 clone 即用）

详见 **[`DEPLOY.md`](DEPLOY.md)**，核心两步：

```powershell
git clone <本仓库地址> && cd xiaot
pwsh sync-skills.ps1      # 部署 13 个 skill + xiaot_memory 到 ~/.xiaot（lib/bin/skills/config.json）
```

记忆命令需要 **Python 3 + PyYAML**（`pip install pyyaml`）。可用
`XIAOT_PYTHON` 环境变量指定 python；默认取 PATH 上的 `python`。
记忆数据位于项目根 `.agent/`（已随仓库保留，不入 git）。

### Codex

读取 `xiaot/AGENTS.md` 即加载小T规则；skills 由 AGENTS 显式引用
（`xiaot/skills/<name>/SKILL.md`），也可复制到 `~/.codex/skills/` 自动发现。

### OpenCode

OpenCode 原生支持 AGENTS.md 与 Anthropic SKILL.md 格式：

- 规则：把 `xiaot/AGENTS.md` 的内容并入项目 AGENTS.md，或复制为项目根
  `AGENTS.md`（OpenCode 优先读取）
- 技能：复制 `xiaot/skills/*` 到 OpenCode 扫描目录（项目或 home）

### 记忆层（内迁，复用 AT 治理语义）

小T 自带三层记忆引擎 `xiaot_memory`：short（临时，必绑 task）→
medium（需证据 + 重提炼 + 确认）→ long（需 verified + 项目归属）。
`bin/xiaot-memory.ps1` 是统一入口，skills 一律 `& $Xiaot.MemoryCmd memory <sub>`。

### 记忆晋升示例（v3.1 严格动词）

一条 short 沉淀到 medium 的完整链路：

```powershell
# 1. 沉淀（short 必绑 task）
& $Xiaot.MemoryCmd memory add memory://session/code-001-fix-beam/short --conclusion "beam 阈值测出为 2" --task 001-fix-beam
# 2. 验证（补证据）
& $Xiaot.MemoryCmd memory verify memory://session/code-001-fix-beam/short --evidence "test:beam<2"
# 3. 结算（默认 dry-run，看分类）
& $Xiaot.MemoryCmd memory settle 001-fix-beam
# 4. 晋升（需确认 + 证据 + 重新提炼，禁复制原文）
& $Xiaot.MemoryCmd memory promote memory://session/code-001-fix-beam/short --to medium --confirmed --evidence "test:beam<2" --distilled "beam 阈值固定为 2，低于则跳过稳定性检查"
```

short 无 `--task`、medium 缺证据/未提炼/未确认、技术事实直写 long，都会被准入规则拒绝。

## 任务编排 CLI（v3.1，Orchestrator + 分层）

xiaot 在记忆层之上新增**任务编排层**：面向 Coding Agent 的编排 CLI（对齐 spec-driven 设计），带记忆开工、留记忆收工。分层：`commands`（薄）→ `orchestrator`（核心，注入端口）→ `ports`（契约），记忆/技能/规范为同级能力。详见 `docs/TASKBOOK-v3.0-orchestrator.md` 与 `ARCHITECTURE-v3.md`。

### 快速开始

```powershell
# 1) 部署：加入 PATH（新终端生效）
powershell -ExecutionPolicy Bypass -File xiaot\bin\setup-xiaot.ps1

# 2) 项目初始化：建 .xiaot 工作区 + 注入 .opencode 编排命令/skill
#    并把"规范项目名"固化为 .xiaot/project.json（缺省 = 项目目录名）
xiaot init --dir <项目路径> [--project <规范名>]

# 3) 编排任务（agent 会话内，按 xiaot-orchestrate skill 自动走）
#    --project 缺省自动回落 init 固化名——跨会话记忆注入依赖同一项目名
xiaot task "开发任务描述"                # 带记忆开工，返回 context 片段
xiaot settle <task_id> --status success --output "<做了什么>" --text "<候选结论>"   # 收工沉淀建议
xiaot confirm "<结论>" --scope project --evidence "<证据>"     # 人工确认写入 medium（project 取固化名）
```

> 项目名纪律：`task`/`settle`/`confirm` 的 `--project` 缺省统一回落
> `.xiaot/project.json`（显式传值优先）。会话内勿自造变体名，否则记忆互相看不见。

### 命令一览

| 命令 | 作用 |
|---|---|
| `task` | 启动/恢复任务闭环（workspace 落盘 + 记忆注入 + context 片段 JSON）|
| `retrieve` | 中途补查任务相关记忆（A 模型：medium/long，引用式）|
| `plan` | 产出并落盘规划文档 |
| `settle` | 收工沉淀：与既有记忆比对 → duplicate/review + scope 建议（**全人工**）|
| `confirm` | 人工确认后把结论写入 medium（task/project scope）——记忆闭环的写入口 |
| `checkpoint` / `timeline` / `rollback` | 任务时间线（workspace+记忆快照）/列表/恢复 |
| `inject` / `init` | 注入编排命令到 agent 目录 / 一键项目初始化 |

### 真实会话闭环（已验证）

在 opencode 会话中输入开发任务，agent 按 `xiaot-orchestrate` 驱动：先 `xiaot task` 拿 context → 执行 → `xiaot checkpoint` 里程碑 → 完成后 `xiaot settle` 出建议 → 你 `xiaot confirm` 落 medium → 下次同项目任务自动注入。内存闭环已实测：settle→confirm 写入→下任务 retrieve 注入到。

## 边界（诚实声明）

- 不依赖外部路由数据库（`routing.md` 做触发词路由，记忆做索引）
- 一次性审批交给宿主（Codex / OpenCode）权限机制，不在小T 内重复实现
- 不做自动欢迎语（改为按需 continue）
- `xiaot-workflow` 依赖 Superpowers（writing-plans / executing-plans 等）：
  Codex 插件内置直接可用；OpenCode 需自行安装 Superpowers 技能——可从
  Codex 插件缓存复制（`~/.codex/plugins/.../superpowers/*/skills/*`）到
  `~/.config/opencode/skills/`，或按 Superpowers 官方文档安装。
- 跨生态已由 OpenCode 官方文档确认支持 AGENTS.md 与 SKILL.md，但具体版本
  行为建议实测（最小验证：同一目录 codex / opencode 各跑一次记忆读写）

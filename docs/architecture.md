# AT 总架构设计（v2 系列）

> 更新日期：2026-08-08 ｜ 分支：v2.0 ｜ 当前目标：v2.1 记忆 MVP

## 1. 定位

AT v2 是**个人辅助开发工具流中的记忆层**：管理三层记忆（short / medium /
long）的可见性、人工操作与生命周期。不替代 Codex、不重复实现
workflow / knowledge / execution，其余全部复用开源技术。

核心问题只有一个：

> 让人（和 Agent）清楚地看到当前记住了什么，并能在需要时查看、提升、回滚。

## 2. 价值主张

长任务下模型上下文"装得下但不划算"：token 线性膨胀、每步变慢、早期信息
注意力衰减。AT 分段让每段上下文保持恒定小区间，段间用 handoff 传递结论；
同时把记忆完全透明给人工，由人做提升与清理决策。

## 3. 版本路线

```text
v2.0  机制验证（已交付）：8 模块 + 三 session 隔离 + 最小 eval
v2.1  记忆 MVP（当前目标）：三层记忆 + 树视图 + 人工操作 + 生命线 + skill
v2.2  复用 Superpowers（workflow 适配）
v2.3  复用 Knowledge（OpenWiki / CodeAlmanac 适配）
v2.4  并行执行（tmux + git worktree）
```

MVP 门槛 = v2.1。v2.2 起全部是复用开源技术的适配层。

## 4. 模块分层

### 核心（自研交付）

| 模块 | 职责 | 载体 |
|---|---|---|
| Memory Manager | 三层存储（Markdown 落盘）、Memory URI、状态机 | `memory.py` |
| Memory View | 树视图：三层全貌、scope 分组、状态/来源/时间 | `view.py` |
| Memory Lifecycle | 人工操作：promote / archive / discard | `memory.py` |
| Timeline | 生命线：checkpoint / timeline / rollback | `timeline.py` |
| Observer | 记忆读写与操作审计事件（JSONL + 时间戳） | `observer.py` |
| CLI | `at memory` 命令族 | `cli.py` |

### 支撑（最小脚手架，不扩展）

Session Registry（`registry.py`）、Context Router / Assembler（`context.py`）、
Policy Engine（`policy.py`）、Handoff Manager（`handoff.py`）——让记忆产生与
流动，保持最小实现。

### 复用层（适配不实现）

- Workflow → **Superpowers**（已装 6.2.0）
- Knowledge → **CodeAlmanac**（macOS-only 需验证）/ **openwiki**（备选）
- Execution → **Codex CLI**（`execution.py` LocalAdapter 已实现）

## 5. v2.1 记忆核心设计

### 5.1 Memory URI 与三层

```text
memory://session/<id>/short     # 单会话，任务结束人工清理
memory://task/<id>/medium       # 任务周期，最重要
memory://feature/<name>/medium
memory://project/<name>/long    # 跨任务，人工 promote 后才进入
memory://role/<role>/long
```

### 5.2 状态机（人工驱动）

```text
candidate ──promote──▶ active ──promote──▶ verified
    │                    │                    │
    └────discard─────────┴────discard─────────┘
                archive（任意状态可归档）
```

- 同层 promote：`candidate→active→verified`，verified 到顶不可再升
- 跨层 promote（`--to`）：文件迁移到目标 tier，状态置 active；来源 verified
  且目标 long 时保持 verified
- archive / discard：文件内全部条目统一置 archived / deprecated

### 5.3 存储格式

```text
.agent/memory/<tier>/<scope>-<name>.md     # 记忆正文：Markdown，追加式，
                                           # YAML 多文档流保真元数据
.agent/timeline/<ts>-<label>/              # 生命线节点
    ├── meta.yaml                          # id / label / created_at / 各层条目数
    └── memory/{short,medium,long}/        # 三层全量快照（复制）
.agent/runtime/events/events.jsonl         # 审计事件（行级 JSON + 时间戳）
```

### 5.4 CLI 命令族

```text
at memory view [--all]              # 树视图（默认活跃，--all 含归档/废弃）
at memory promote <uri> [--to]      # 人工提升（可跨层）
at memory archive <uri>             # 归档
at memory discard <uri>             # 废弃
at memory checkpoint <label>        # 打生命线节点（全量快照）
at memory timeline                  # 查看时间线
at memory rollback <node>           # 回滚（自动先打恢复点）

at init / at task run / at eval / at doctor   # 支撑命令
```

### 5.5 skill 触发（时间节点）

- 位置：`C:\Users\kk\.codex\skills\at-memory-checkpoint`
- 触发词：用户说"打点 / 记录时间节点 / 存个档 / checkpoint"等意图时触发
- 动作：运行 `at memory checkpoint <label>`，记录开发里程碑到生命线

## 6. v2.0 隔离机制（支撑记忆产生与流动）

- **Context 构建时隔离**：每 session 从零组装 Context Bundle，无会话继承；
  注入前按 role read 白名单过滤，被拒项记入 `bundle.policy.filtered`
- **Memory 存储层隔离**：tier 目录 + scope 前缀双隔离，无全局遍历 API
- **Scope 读侧强制**：Policy 读过滤已接线；写侧 `can_write` 待接线（v2.1
  信任模型决策点）
- **进程级隔离**：每 session 一个新 Codex 进程，无会话连续性
- **Structured Handoff**：段间唯一数据通道，不复制完整对话

## 7. 一次任务的数据流

```text
create_task → create_session → build_context（Policy 过滤）
  → LocalAdapter（spawn Codex）→ collect output
  → create_handoff（注入下一 session）
  → 关键节点人工触发 at memory checkpoint（打生命线）
  → 任务中沉淀的记忆由人 promote 到 medium / long
```

## 8. 目录结构

```text
project/
├── AGENTS.md
├── src/at_runtime/          # 核心实现
├── tests/                   # 单元测试
├── docs/                    # 架构 / spec / plan
└── .agent/                  # v2 本地运行时数据（gitignored）
    ├── manifest.yaml / policies.yaml
    ├── runtime/{sessions,tasks,events}/
    ├── memory/{short,medium,long}/
    ├── timeline/<ts>-<label>/
    ├── handoffs/
    ├── artifacts/
    └── knowledge/refs/
```

v2 本地存放 `.agent/` 与 v1 的 `.at/` 完全隔离（v2 代码对 `.at` 零引用，
两者均 gitignored）。

## 9. 边界与已知限制（诚实声明）

1. **隔离是 API/命名空间级（软隔离）**：读侧强制、写侧待接线；执行 sandbox
   限制是 v2.1 信任模型决策点
2. **relevance 显式引用**：无 LLM 检索，检索留待复用层
3. **不做**：自动 GC / 自动提升 / 自动摘要 / Web 面板 / 语言翻译链路
4. **无 DB / Web / 网络依赖**（除 Codex 自身）；PyYAML 唯一新增依赖
5. v2.1 前：`at memory view/promote/checkpoint/timeline/rollback` 与 skill
   尚未实现（见实现计划）

## 10. 文档索引

- 详细设计：`docs/superpowers/specs/2026-08-08-at-v2-context-runtime-design.md`
- 实现计划：`docs/superpowers/plans/2026-08-08-at-v2-1-memory-mvp-implementation-plan.md`
- 快速总览：`docs/architecture-v2.md`
- 开发原则：`docs/developing-at-v2.md`

# AT 总架构设计（v2 系列）

> 更新日期：2026-08-08 ｜ 分支：v2.0 ｜ 当前目标：v2.1 记忆层 MVP

## 1. 定位

AT v2 是**个人辅助开发工具流中的记忆层**：管理三层记忆（short / medium /
long）的可见性、人工操作与生命周期。**不编排 agent、不重复实现
workflow / knowledge / execution**——这些全部复用开源技术。

核心问题只有一个：

> 让人（和 Agent）清楚地看到当前记住了什么，并能在需要时查看、写入、提升、回滚。

## 2. 价值主张

长任务下模型上下文"装得下但不划算"：token 线性膨胀、每步变慢、早期信息
注意力衰减。AT 把开发过程中的结论、约束、未决问题结构化沉淀为三层记忆，
让人（和后续会话）随时看到"系统记住了什么"；提升与清理由人决策。

## 3. 版本路线

```text
v2.0  机制验证（已交付）：隔离与编排机制的可行性验证件
v2.1  记忆层 MVP（当前目标）：三层记忆 + 结构化写入 + 树视图 + 人工操作
      + 生命线 + skill 触发
v2.2  复用 Superpowers（workflow 适配）
v2.3  复用 Knowledge（OpenWiki / CodeAlmanac 适配）
v2.4  并行执行（tmux + git worktree）
```

MVP 门槛 = v2.1。v2.2 起全部是复用开源技术的适配层。

## 4. 模块分层

### 核心（自研交付）

| 模块 | 职责 | 载体 |
|---|---|---|
| Memory Manager | 三层存储、Memory URI、状态机操作 | `memory.py` |
| Memory Write | 结构化写入（结论/约束/未解决三字段） | `memory.py` + CLI |
| Memory View | 树视图（short 折叠、medium/long 全显） | `view.py` |
| Memory Lifecycle | promote（跨层跨 scope）/ archive / discard | `memory.py` |
| Timeline | 生命线：checkpoint / timeline / rollback | `timeline.py` |
| Observer | 记忆操作审计事件（JSONL + 时间戳） | `observer.py` |
| CLI | `at memory` 命令族 | `cli.py` |

### V0.1 验证件（保留代码，移出核心，不再扩展）

`registry.py`、`context.py`、`policy.py`、`handoff.py`、`runner.py`、
`eval.py`、`execution.py`——v2.0 验证隔离与编排机制的产物，代码保留供参考。

### 复用层（适配不实现）

- Workflow → **Superpowers**（已装 6.2.0）
- Knowledge → **CodeAlmanac**（macOS-only 需验证）/ **openwiki**（备选）
- Execution → **Codex CLI**

## 5. v2.1 记忆核心设计

### 5.1 Memory URI 与三层

```text
memory://session/<id>/short     # 单会话草稿，任务结束人工清理
memory://task/<id>/medium       # 任务级，跨会话共享
memory://feature/<name>/medium
memory://project/<name>/long    # 项目级，人工 promote 后进入
memory://role/<role>/long
```

### 5.2 状态机（人工驱动）

```text
candidate ──promote──▶ active ──promote──▶ verified
    │                    │                    │
    └────discard─────────┴────discard─────────┘
                archive（任意状态可归档）
```

**promote 跨层同时迁移 scope**：`session → task`、`task → project`，
保证提升后的记忆归属到正确的共享维度（否则其他会话按任务维度找不到）。

### 5.3 结构化写入（三字段）

```text
at memory write <uri> \
  --conclusion "..." \
  --constraint "..." \
  --unresolved "..."
```

- 三字段允许部分缺失；全部缺失报错不落盘
- 写入后 status=candidate，记录审计事件
- 写入由外部触发（Codex / Superpowers / 人工），AT 不编排

### 5.4 存储格式

```text
.agent/memory/<tier>/<scope>-<name>.md     # Markdown 追加式，
                                           # YAML 多文档流保真元数据
.agent/timeline/<ts>-<label>/              # 生命线节点
    ├── meta.yaml                          # id / label / created_at / 各层条目数
    └── memory/{short,medium,long}/        # 三层全量快照
.agent/runtime/events/events.jsonl         # 审计事件
```

## 6. CLI

```text
at memory write <uri> --conclusion ... [--constraint ...] [--unresolved ...]
at memory get <uri>                    # 结构化读取（供 Agent 调用）
at memory view [--all]
at memory promote <uri> [--to medium|long]
at memory archive <uri>
at memory discard <uri>
at memory checkpoint <label>
at memory timeline
at memory rollback <node>

at doctor   # 健康检查（支撑）
```

## 7. 触发机制（外部驱动）

- **写入**：Codex / Superpowers / 人工在阶段完成时调用 `at memory write`
  （AGENTS.md 约定）
- **打点**：`at-memory-checkpoint` skill 用触发词（"打点 / 记录时间节点 /
  存个档 / checkpoint"）调用 `at memory checkpoint`

## 8. 目录结构

```text
project/
├── AGENTS.md
├── src/at_runtime/          # 核心实现
├── tests/
├── docs/
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

1. **记忆质量依赖写入方**：agent / 人工负责提供结构化内容，噪音控制靠
   AGENTS.md 约定与审计事件
2. **V0.1 验证件移出核心**：隔离 / 编排机制已实现但不再承诺为 AT 能力
3. **不做**：自动 GC / 自动提升 / 自动摘要 / Web 面板
4. **无 DB / Web / 网络依赖**；PyYAML 唯一新增依赖
5. v2.1 前：`at memory write/view/promote/checkpoint/timeline/rollback`
   与 skill 尚未实现（见实现计划）

## 10. 文档索引

- 详细设计：`docs/superpowers/specs/2026-08-08-at-v2-context-runtime-design.md`
- 实现计划：`docs/superpowers/plans/2026-08-08-at-v2-1-memory-mvp-implementation-plan.md`
- 快速总览：`docs/architecture-v2.md`
- 开发原则：`docs/developing-at-v2.md`

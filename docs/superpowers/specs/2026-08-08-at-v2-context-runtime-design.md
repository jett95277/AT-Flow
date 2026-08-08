# AT v2 Context Runtime Design（记忆层版 2026-08-08）

## Goal

AT v2 是**个人辅助开发工具流中的记忆层**：管理三层记忆（short / medium /
long）的可见性、人工操作与生命周期。**不编排 agent、不重复实现
workflow / knowledge / execution**——这些全部复用开源技术。

核心问题只有一个：

> 让人（和 Agent）清楚地看到当前记住了什么，并能在需要时查看、写入、提升、回滚。

## 定位边界（v2 收敛后的重要修正）

### AT 做（核心交付）

- 三层记忆存储 + 状态机
- 结构化写入接口（结论 / 约束 / 未解决问题三字段）
- 树视图（三层全貌）
- 人工操作（promote / archive / discard）
- 生命线（checkpoint / timeline / rollback）
- 审计事件（写入 / 操作 / 打点 / 回滚）

### AT 不做（V0.1 机制验证件，代码保留但移出核心、不再扩展）

- agent 角色编排（analysis / code / test 流水线）——交给 Superpowers
- 上下文隔离机制（Context Router / Policy 权限矩阵 / Handoff 链条）——
  是 v2.0 验证隔离用的机制，不是记忆层的交付物
- Session Registry / runner / eval——V0.1 验证件

### 复用层（适配不实现）

- Workflow → **Superpowers**（已装 6.2.0）
- Knowledge → **CodeAlmanac**（macOS-only 需验证）/ **openwiki**（备选）
- Execution → **Codex CLI**

## 价值主张

长任务下模型上下文"装得下但不划算"：token 线性膨胀、每步变慢、早期信息
注意力衰减。AT 把开发过程中的结论、约束、未决问题结构化沉淀为三层记忆，
让人（和后续会话）随时看到"系统记住了什么"；提升与清理由人决策。

## 版本路线

```text
v2.0  机制验证（已交付）：隔离与编排机制的可行性验证件
v2.1  记忆层 MVP（当前目标）：三层记忆 + 结构化写入 + 树视图 + 人工操作
      + 生命线 + skill 触发
v2.2  复用 Superpowers（workflow 适配）
v2.3  复用 Knowledge（OpenWiki / CodeAlmanac 适配）
v2.4  并行执行（tmux + git worktree）
```

MVP 门槛 = v2.1：记忆核心交付完成、可日常使用。v2.2 起全部是复用适配层。

## 核心设计原则

1. **记忆可见**：记忆是给人看的，Markdown 实时落盘，目录即视图。
2. **记忆有 Scope**：任何记忆都有归属（session / task / feature / project /
   role），scope 是归类维度，不是权限单元。
3. **记忆流动靠人**：promotion / 清理是人工决策，不做自动 GC 与自动提炼。
4. **生命周期可回滚**：生命线节点全量快照，随时查看、可回滚（回滚前自动
   打恢复点）。
5. **其他全部复用**：workflow / knowledge / execution 一律复用开源，不自研。

## 模块分层

### 核心（自研交付）

| 模块 | 职责 | 载体 |
|---|---|---|
| Memory Manager | 三层存储、Memory URI、状态机操作 | `memory.py` |
| Memory Write | 结构化写入（结论/约束/未解决三字段） | `memory.py` + CLI |
| Memory View | 树视图（short 折叠、medium/long 全显） | `view.py` |
| Memory Lifecycle | 人工操作：promote（跨层跨 scope）/ archive / discard | `memory.py` |
| Timeline | 生命线：checkpoint / timeline / rollback | `timeline.py` |
| Observer | 记忆操作审计事件（JSONL + 时间戳） | `observer.py` |
| CLI | `at memory` 命令族 | `cli.py` |

### V0.1 验证件（保留代码，移出核心，不再扩展）

`registry.py`、`context.py`、`policy.py`、`handoff.py`、`runner.py`、
`eval.py`、`execution.py`（LocalAdapter）——v2.0 验证隔离与编排机制的
产物，代码保留供参考，不属于 v2.1 交付范围。

### 复用层

- Workflow → Superpowers
- Knowledge → CodeAlmanac / openwiki
- Execution → Codex CLI

## 数据模型

### Memory URI 与三层

```text
memory://session/<id>/short     # 单会话草稿，任务结束人工清理
memory://task/<id>/medium       # 任务级，跨会话共享
memory://feature/<name>/medium
memory://project/<name>/long    # 项目级，人工 promote 后进入
memory://role/<role>/long
```

### 状态机（人工驱动）

```text
candidate ──promote──▶ active ──promote──▶ verified
    │                    │                    │
    └────discard─────────┴────discard─────────┘
                archive（任意状态可归档）
```

promote 规则：

- 同层：`candidate → active → verified`，verified 到顶
- 跨层（`--to`）：**同时迁移 scope**——`session → task`（用写入方提供的
  task 归属）、`task → project`（用 task 的 project 归属）；来源 verified
  且目标 long 时保持 verified

### 结构化写入（三字段）

```text
at memory write <uri> \
  --conclusion "beam < 2 意味着 stability 判定被跳过" \
  --constraint "保持 scoring API schema 不变" \
  --unresolved "阈值是否应改为配置项，待确认"
```

- 三字段允许部分缺失（缺的字段写空数组）
- 全部缺失时报错，不落盘
- 写入后 status=candidate，记录审计事件

### 存储格式

```text
.agent/memory/<tier>/<scope>-<name>.md     # Markdown 追加式，
                                           # YAML 多文档流保真元数据
.agent/timeline/<ts>-<label>/              # 生命线节点
    ├── meta.yaml                          # id / label / created_at / 各层条目数
    └── memory/{short,medium,long}/        # 三层全量快照
.agent/runtime/events/events.jsonl         # 审计事件
```

## CLI 边界

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

## 触发机制（外部驱动）

AT 不做编排，因此写入与打点全部由外部触发：

- **写入**：Codex / Superpowers / 人工在阶段完成时调用
  `at memory write`（AGENTS.md 约定，无需 skill）
- **读取**：后续 Codex 会话按需调用 `at memory get <uri>` 获取结构化记忆
- **打点**：`at-memory-checkpoint` skill 用触发词（"打点 / 记录时间节点 /
  存个档 / checkpoint"）调用 `at memory checkpoint <label>`

## 验证门（v2.1）

1. `at memory write` 三字段正确落盘，部分缺失允许、全缺失拒绝
2. `at memory get` 结构化读取与写入一致（Agent 读取入口可用）
3. `at memory view` 树视图正确展示（short 折叠、medium/long 全显）
4. promote / archive / discard 状态流转正确；跨层 promote 同时迁移 scope
5. checkpoint 生成全量快照；timeline 列出节点；rollback 恢复并先打恢复点
6. checkpoint skill 触发词可触发打点
7. 写 / 操作 / 打点 / 回滚均记录审计事件（memory.write / promoted /
   archived / discarded / checkpoint / rollback）
8. 全量单元测试 + `at doctor` 通过

## 风险与务实决策

1. **记忆质量依赖写入方**：agent / 人工负责提供结构化内容，噪音控制靠
   AGENTS.md 约定与审计事件（`memory.write` 记录写入方与内容长度）。
2. **不做自动机制**：自动 GC、自动提升、自动摘要、Web 面板。
3. **无 DB / Web / 网络依赖**；PyYAML 唯一新增依赖。
4. **V0.1 验证件的边界如实标注**：隔离 / 编排机制已实现但移出核心，不承诺
   作为 AT 能力；如需重新启用，按 v2.2+ 的复用层评估。

## 技术栈与存储

- Python 3.10+；PyYAML。
- 文件系统存储：Markdown（记忆正文/快照）、YAML（元数据/策略）、JSON（事件）。
- v2 本地存放 `.agent/` 与 v1 的 `.at/` 完全隔离，均 gitignored。

## 与 v1 / v2.0 的关系

- v1：多 Agent 编排平台，实战效果差（编排成本大于产出）。
- v2.0：隔离与编排机制验证（已交付，代码保留为验证件）。
- v2.1：收敛为记忆层，只保留"记忆"这一有确定性价值的核心，其余复用开源。

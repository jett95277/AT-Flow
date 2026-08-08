# AT Runtime v2 架构与能力总览

> 更新日期：2026-08-08 ｜ 分支：v2.0 ｜ 当前目标：v2.1 记忆 MVP

## 1. 定位与核心问题

AT v2 是**个人辅助开发工具流中的记忆层**。它不替代 Codex、不重复实现
workflow / knowledge / execution，只负责：

> **让人（和 Agent）清楚地看到当前记住了什么，并能在需要时查看、提升、回滚。**

核心交付：三层记忆（short / medium / long）的**可见性与人工操作**——
Markdown 落盘、树视图、promote / archive / discard、生命线
（checkpoint / timeline / rollback）。

## 2. 价值主张

长任务下上下文"装得下但不划算"：token 线性膨胀、每步变慢、早期信息注意力
衰减。AT 分段让每段上下文保持恒定，段间用 handoff 传递结论；同时把记忆
完全透明给人工，由人做提升与清理决策。

## 3. 版本路线

```text
v2.0  机制验证（已交付）：8 模块最小可用 + 三 session 隔离 + 最小 eval
v2.1  记忆 MVP（当前目标）：三层记忆 + 树视图 + 人工操作 + 生命线 + skill
v2.2  复用 Superpowers（workflow 适配）
v2.3  复用 Knowledge（OpenWiki / CodeAlmanac 适配）
v2.4  并行执行（tmux + git worktree）
```

MVP 门槛 = v2.1。v2.2 起全部是复用开源技术的适配层。

## 4. 模块分层

### 核心（自研交付）

| 模块 | 职责 |
|---|---|
| Memory Manager | 三层存储（Markdown 落盘）、Memory URI、状态机 |
| Memory View | 树视图：三层全貌、scope 分组、状态/来源/时间 |
| Memory Lifecycle | 人工操作：promote / archive / discard |
| Timeline | 生命线：checkpoint / timeline / rollback |
| Observer | 记忆读写与操作审计事件（JSONL + 时间戳） |
| CLI | `at memory` 命令族 |

### 支撑（最小脚手架，不扩展）

Session Registry、Context Router / Assembler、Policy Engine、Handoff
Manager——让记忆产生与流动，保持最小实现。

### 复用层（适配不实现）

- Workflow → **Superpowers**（已装）
- Knowledge → **CodeAlmanac**（macOS-only 需验证）/ **openwiki**（备选）
- Execution → **Codex CLI**（LocalAdapter 已实现）

## 5. 数据模型

### Memory URI 与三层

```text
memory://session/<id>/short     # 单会话，任务结束人工清理
memory://task/<id>/medium       # 任务周期，最重要
memory://project/<name>/long    # 跨任务，人工 promote 后才进入
```

### 状态机（人工驱动）

```text
candidate ──promote──▶ active ──promote──▶ verified
    │                    │                    │
    └────discard─────────┴────discard─────────┘
                archive（任意状态可归档）
```

### 存储

- 记忆正文：`.agent/memory/<tier>/<scope>-<name>.md`（Markdown，追加式，
  YAML 多文档流保真元数据）
- 生命线：`.agent/timeline/<ts>-<label>/`（meta.yaml + 三层全量快照）
- 事件：`.agent/runtime/events/events.jsonl`（行级 JSON + 时间戳）

## 6. CLI

```text
at memory view [--all]
at memory promote <uri> [--to]
at memory archive <uri>
at memory discard <uri>
at memory checkpoint <label>
at memory timeline
at memory rollback <node>

at init / at task run / at eval / at doctor   # 支撑命令
```

正常使用由 Codex 通过 AGENTS.md / Skills 调用——例如 checkpoint skill 用
触发词（"打点 / 记录时间节点 / 存个档"）触发 `at memory checkpoint`。

## 7. 当前状态与已知边界（诚实声明）

- V0.1 已交付：8 模块、三 session 隔离、最小 eval、24 个测试全绿、真实
  Codex 冒烟通过。
- v2.1 待实现：树视图、promote/archive/discard、checkpoint/timeline/
  rollback、checkpoint skill。
- 隔离是 API/命名空间级（软隔离）：读侧 Policy 过滤已强制，写侧 `can_write`
  未接线；执行 sandbox 限制是 v2.1 信任模型决策点。
- 明确不做：自动 GC / 自动提升 / 自动摘要 / Web 面板 / 语言翻译链路。

设计详见
`docs/superpowers/specs/2026-08-08-at-v2-context-runtime-design.md`；
开发原则见 `docs/developing-at-v2.md`。

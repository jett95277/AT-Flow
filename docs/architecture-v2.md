# AT Runtime v2 架构与能力总览

> 更新日期：2026-08-08 ｜ 分支：v2.0 ｜ 当前目标：v2.1 记忆层 MVP

## 1. 定位

AT v2 是**个人辅助开发工具流中的记忆层**：管理三层记忆（short / medium /
long）的可见性、人工操作与生命周期。不编排 agent、不重复实现
workflow / knowledge / execution——全部复用开源技术。

核心问题：

> 让人（和 Agent）清楚地看到当前记住了什么，并能在需要时查看、写入、提升、回滚。

## 2. 版本路线

```text
v2.0  机制验证（已交付）：隔离与编排机制验证件
v2.1  记忆层 MVP（当前目标）：三层记忆 + 结构化写入 + 树视图 + 人工操作
      + 生命线 + skill 触发
v2.2  复用 Superpowers（workflow 适配）
v2.3  复用 Knowledge（OpenWiki / CodeAlmanac 适配）
v2.4  并行执行（tmux + git worktree）
```

## 3. 核心能力（v2.1 交付）

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
```

关键设计：

- **结构化写入三字段**（结论 / 约束 / 未解决问题），部分缺失允许、全缺失拒绝
- **promote 跨层同时迁移 scope**（session→task→project），保证提升后归属正确
- **short 折叠 / medium / long 全显**，`--all` 展开
- **checkpoint 全量快照 + rollback 自动恢复点**
- **写入与打点外部触发**（Codex / Superpowers / 人工 + checkpoint skill）

## 4. 模块

核心：`memory.py`（存储/状态机/写入）、`view.py`（树）、`timeline.py`
（生命线）、`observer.py`（审计）、`cli.py`。

V0.1 验证件（保留不扩展）：registry / context / policy / handoff / runner /
eval / execution。

复用：Superpowers（workflow）、CodeAlmanac / openwiki（knowledge）、
Codex CLI（execution）。

## 5. 存储

```text
.agent/memory/<tier>/<scope>-<name>.md     # 记忆正文（Markdown + YAML 元数据）
.agent/timeline/<ts>-<label>/              # 生命线快照
.agent/runtime/events/events.jsonl         # 审计事件
```

## 6. 边界

- 记忆质量依赖写入方（agent / 人工），噪音控制靠约定 + 审计
- 不做自动 GC / 自动提升 / 自动摘要 / Web 面板
- 无 DB / Web / 网络依赖；`.agent/` 与 v1 `.at/` 完全隔离

详细设计见
`docs/superpowers/specs/2026-08-08-at-v2-context-runtime-design.md`；
总架构见 `docs/architecture.md`；开发原则见 `docs/developing-at-v2.md`。

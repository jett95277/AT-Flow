# AT Runtime

**A memory layer for personal AI-assisted development workflows.**

中文定位：**个人辅助开发工具流中的记忆层**。

AT Runtime 不替代 Codex、不编排 Agent、不重复实现 Workflow / Knowledge /
Execution（这些全部复用开源技术）。它只负责三层记忆（short / medium /
long）的可见性、人工操作与生命周期，专门解决：

- 开发过程中的结论、约束、未决问题没有沉淀
- 多会话 / 多天开发时记忆分散、看不到系统记住了什么
- 无法回顾"为什么这么决策"，无法回滚到关键时间节点
- 记忆提升 / 清理完全依赖人工，缺少结构化视图辅助决策

AT Runtime 的核心问题只有一个：

> **让人（和 Agent）清楚地看到当前记住了什么，并能在需要时查看、写入、提升、回滚。**

## 大框架（四层解耦）

```text
User
  → Coding Agent（Codex / Claude Code / OpenCode）—— 唯一主要交互入口
  → Superpowers（Workflow）—— 负责：怎么做（复用）
  → AT Runtime（Memory Layer）—— 负责：记住什么 ★ 本系统
  → Execution（Codex CLI / tmux+worktree）—— 负责：在哪里运行（复用）
  → Knowledge（OpenWiki / CodeAlmanac）—— 负责：项目已知什么（复用）
```

## 核心原则

1. **记忆可见**——记忆是给人看的，Markdown 实时落盘，目录即视图。
2. **记忆有 Scope**——任何记忆都有归属（session/task/feature/project/role）。
3. **记忆流动靠人**——promotion / 清理是人工决策，不做自动 GC。
4. **生命周期可回滚**——生命线节点全量快照，回滚前自动打恢复点。
5. **其他全部复用**——workflow / knowledge / execution 一律复用开源，不自研。

## 核心模块

```text
Memory Manager  —— 三层存储 + 状态机（promote/archive/discard）
Memory Write    —— 结构化写入（结论/约束/未解决问题三字段）
Memory View     —— 树视图（short 折叠，medium/long 全显）
Timeline        —— 生命线（checkpoint / timeline / rollback）
Runtime Observer—— 记忆操作审计事件
CLI             —— at memory 命令族
```

V0.1 验证件（registry / context / policy / handoff / runner / eval /
execution）保留代码、移出核心，不再扩展。

## 记忆层数据流

```text
阶段完成（Codex / Superpowers / 人工触发）
  → at memory write <uri>（结论/约束/未解决三字段）→ short candidate
  → at memory view（人工查看三层树）
  → at memory promote（人工提升，跨层同时迁移 scope）
  → at memory checkpoint（关键节点打生命线快照）
  → at memory rollback（需要时回滚，自动先打恢复点）
```

## 版本路线

```text
v2.0   机制验证（已交付）：隔离与编排机制的可行性验证件
v2.1   记忆层 MVP（当前目标）：三层记忆 + 结构化写入 + 树视图 + 人工操作
       + 生命线 + skill 触发
v2.2   复用 Superpowers（workflow 适配）
v2.3   复用 Knowledge（OpenWiki / CodeAlmanac 适配）
v2.4   并行执行（tmux + git worktree）
```

## 目录结构

```text
project/
├── AGENTS.md
├── src/at_runtime/       # 核心实现
├── tests/
├── docs/
└── .agent/               # v2 本地运行时数据（gitignored）
    ├── manifest.yaml / policies.yaml
    ├── memory/           # short / medium / long
    ├── timeline/         # checkpoint 快照
    ├── runtime/events/   # 审计事件（events.jsonl）
    └── runtime/          # sessions / tasks（V0.1 验证件目录）
```

v2 本地存放 `.agent/` 与 v1 的 `.at/` 完全隔离（v2 代码对 `.at` 零引用，
两者均 gitignored）。

## 快速开始（当前可用）

```powershell
# Python 3.10+，仓库内建虚拟环境后安装
python -m venv .venv
.venv\Scripts\python -m pip install -e .

# 初始化 .agent 工作区
.venv\Scripts\at init

# 检查工作区健康
.venv\Scripts\at doctor

# 写入结构化记忆（结论 / 约束 / 未解决问题）
.venv\Scripts\at memory write memory://session/s1/short --conclusion "beam < 2 skipped" --constraint "keep schema" --unresolved "threshold config?" --task T17

# 查看三层记忆树 / 读取 / 人工操作
.venv\Scripts\at memory view
.venv\Scripts\at memory get memory://session/s1/short
.venv\Scripts\at memory promote memory://session/s1/short --to medium

# 生命线：打点 / 时间线 / 回滚
.venv\Scripts\at memory checkpoint "fix beam stability"
.venv\Scripts\at memory timeline
.venv\Scripts\at memory rollback 20260808T114110-fix-beam-stability

# 导出三层记忆为 Markdown 报告
.venv\Scripts\at memory export
```

v2.1 记忆层命令族（`at memory write / get / view / promote / archive /
discard / checkpoint / timeline / rollback / export`）已实现，实现计划见
`docs/superpowers/plans/2026-08-08-at-v2-1-memory-mvp-implementation-plan.md`。

## 文档索引

- 详细设计：`docs/superpowers/specs/2026-08-08-at-v2-context-runtime-design.md`
- 实现计划：`docs/superpowers/plans/2026-08-08-at-v2-1-memory-mvp-implementation-plan.md`
- 总架构：`docs/architecture.md`
- 快速总览：`docs/architecture-v2.md`
- 开发原则：`docs/developing-at-v2.md`

## 与 v1 的关系

v1（AT Flow）是"多 Agent 编排平台"，实战中编排开销大于产出。v2.0 在
`v2.0` 分支上重写为隔离与编排机制验证件（代码保留供参考）；v2.1 收敛为
记忆层，只保留"记忆"这一有确定性价值的核心，其余复用开源。v1 代码完整
保留在 git 历史中。

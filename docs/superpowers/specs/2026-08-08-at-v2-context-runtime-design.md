# AT v2 Context Runtime Design（整合版 2026-08-08）

## Goal

AT v2 是**个人辅助开发工具流中的记忆层**。它不替代 Codex、不重复实现
workflow/knowledge/execution，只负责一件事：

> **让人（和 Agent）清楚地看到当前记住了什么，并能在需要时查看、提升、回滚。**

核心交付物是三层记忆的**可见性与人工操作**：Markdown 落盘（目录即视图）、
树视图、promote/archive/discard、生命线（checkpoint/timeline/rollback）。
上下文隔离是让记忆产生与流动的支撑机制，不是交付物。

## 价值主张

长任务下模型上下文"装得下但不划算"：token 线性膨胀、每步变慢、早期信息
注意力衰减。AT 分段让**每段上下文保持恒定小区间**，段间用 handoff 传递结论；
同时把"系统记住了什么"完全透明给人工，由人做记忆提升与清理决策。

## 版本路线（v2 系列）

```text
v2.0  机制验证（已交付）：8 模块最小可用 + 三 session 隔离 + 最小 eval
v2.1  记忆 MVP（当前目标）：三层记忆 + 树视图 + 人工操作 + 生命线 + skill 触发
v2.2  复用 Superpowers：workflow 适配层（怎么做）
v2.3  复用 Knowledge：OpenWiki / CodeAlmanac 适配层（项目已知什么）
v2.4  并行执行：tmux + git worktree（在哪运行）
```

MVP 门槛是 **v2.1**：记忆核心交付完成、可日常使用。v2.2 起全部是"复用
开源技术的适配层"，不是自研。

## 四层解耦（AT 角色收缩）

```text
Superpowers → 怎么做（workflow）            ← 复用，不实现
AT Runtime  → 记住什么（三层记忆 + 生命线）★ 核心交付
Execution   → 在哪里运行（Codex CLI）        ← 复用，不实现
Knowledge   → 项目已知什么（OpenWiki/CodeAlmanac）← 复用，不实现
```

稳定的是协议对象：**Memory、Scope、Status、Timeline**；其余（workflow /
knowledge / execution）都是可替换 Adapter。

## 核心设计原则

1. **记忆可见**：记忆是给人看的，Markdown 实时落盘，目录即视图。
2. **记忆有 Scope**：任何记忆都有归属（session/task/feature/project/role）。
3. **记忆流动靠人**：promotion / 清理是人工决策，不做自动 GC 与自动提炼。
4. **生命周期可回滚**：生命线节点全量快照，随时查看、可回滚（回滚前自动
   打恢复点）。
5. **其他全部复用**：workflow/knowledge/execution 一律复用开源，不自研。

## 模块分层

### 核心（自研交付）

| 模块 | 职责 |
|---|---|
| Memory Manager | 三层存储（Markdown 落盘）、Memory URI、状态机 |
| Memory View | 树视图：三层全貌、scope 分组、状态/来源/时间 |
| Memory Lifecycle | 人工操作：promote / archive / discard |
| Timeline | 生命线：checkpoint（快照）/ timeline（列表）/ rollback（恢复） |
| Observer | 记忆读写与操作审计事件（JSONL + 时间戳） |
| CLI | `at memory` 命令族 |

### 支撑（最小脚手架，不扩展）

| 模块 | 职责 |
|---|---|
| Session Registry | 记录谁在做什么任务 |
| Context Router / Assembler | 组装 Context Bundle（服务记忆注入） |
| Policy Engine | role read/write 白名单（读侧过滤已接线） |
| Handoff Manager | 段间结论传递（结构化 handoff） |

### 复用层（适配不实现）

- Workflow → **Superpowers**（本机已装 6.2.0，V0.2 接入无风险）
- Knowledge → **CodeAlmanac**（首选，macOS-only 需验证）/ **openwiki**（备选）
- Execution → **Codex CLI**（LocalAdapter 已实现；并行执行 V0.4 自建
  tmux+worktree，不依赖 TUI 型三方工具）

## 数据模型

### Memory URI

```text
memory://session/<id>/short
memory://task/<id>/medium
memory://feature/<name>/medium
memory://project/<name>/long
memory://role/<role>/long
```

### 三层定义

- **Short**：单 Session/Stage，高频变化，任务结束由人工清理。
- **Medium**：Task/Feature 周期，保存 root cause、约束、失败尝试、决策；
  最重要的一层。
- **Long**：跨任务、稳定、已验证、项目级；必须经过人工 promote。

### 状态机（人工驱动）

```text
candidate ──promote──▶ active ──promote──▶ verified
    │                    │                    │
    └────discard─────────┴────discard─────────┘
                archive（任意状态可归档）
```

### 存储格式

- 记忆正文：Markdown，`.agent/memory/<tier>/<scope>-<name>.md`，追加式，
  YAML 多文档流保存元数据（content/source/status/created_at 保真）。
- 生命线：`.agent/timeline/<ts>-<label>/`，含 `meta.yaml`（时间/标签/来源）
  与三层全量快照 Markdown。
- 事件：`.agent/runtime/events/events.jsonl`，行级 JSON + 时间戳。

## CLI 边界

```text
at memory view [--all]              # 树视图（默认活跃，--all 全状态）
at memory promote <uri> [--to]      # 人工提升（可跨层）
at memory archive <uri>             # 归档
at memory discard <uri>             # 废弃
at memory checkpoint <label>        # 打生命线节点（全量快照）
at memory timeline                  # 查看时间线
at memory rollback <node>           # 回滚（自动先打恢复点）

at init / at task run / at eval / at doctor   # 支撑命令
```

正常使用中用户不直接敲命令——Codex 通过 AGENTS.md / Skills 调用（例如
checkpoint skill 用触发词触发 `at memory checkpoint`）。

## Skill 触发（时间节点）

- 位置：`C:\Users\kk\.codex\skills`（全局自动发现）
- 触发词：对话中出现"打点 / 记录时间节点 / 存个档 / checkpoint"等意图时，
  Codex 运行 `at memory checkpoint <label>`
- 生命周期：每次开发的关键时间节点（阶段完成、重大决策、发现/修复）由人
  触发记录，形成可查看、可回滚的开发时间线

## 验证门（v2.1）

1. `at memory view` 树视图正确展示三层、scope、状态、来源、时间
2. memory 写读往返保真（多行 content、嵌套 source）
3. promote / archive / discard 状态流转正确且落盘
4. checkpoint 生成全量快照；timeline 列出节点；rollback 恢复并先打恢复点
5. checkpoint skill 触发词可触发打点
6. 全量单元测试 + `at doctor` 通过

## 风险与务实决策

1. **隔离是 API/命名空间级（软隔离）**：执行层 agent 与 runtime 共享文件
   系统；读侧 Policy 过滤已强制，写侧 `can_write` 待接线；执行 sandbox
   限制（`.agent/` 只读/不可见）作为 v2.1 的信任模型决策点。
2. **relevance 显式引用**：Context Router 不做 LLM 检索，relevance = 显式
   声明 + 静态 Policy + 默认最小集；检索留待复用层。
3. **进程级隔离**：每 session 一个新 Codex 进程，无会话连续性。
4. **最小对比 eval**：baseline 单会话 vs AT 三 session，对比成功/token/
   handoff 充分性；完整 Benchmark 不做。
5. **不做**：自动 GC、自动提升、自动摘要、Web 面板、语言翻译链路。

## 技术栈与存储

- Python 3.10+；PyYAML 唯一新增依赖。
- 文件系统存储：Markdown（记忆正文/快照）、YAML（元数据/策略）、JSON（事件）。
- 无数据库、无 Web 框架、无网络依赖（Codex provider 通过现有 CLI 进程调用）。
- v2 本地存放 `.agent/` 与 v1 的 `.at/` 完全隔离，均 gitignored。

## 与 v1 的关系

- `v2.0` 分支仓库内重写，v1 实现完整保留在 git 历史。
- 复用 v1 经验但不迁移代码：不做语言翻译、不做 Web/云、不做重型状态机。
- v1 教训：编排成本大于产出；v2 只保留"记忆"这一有确定性价值的部分。

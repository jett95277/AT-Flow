# AT Runtime

**A context-isolated runtime for long-running and parallel coding agents.**

中文定位：**面向长任务与并行 Coding Agent 的上下文隔离运行时**。

AT Runtime 不负责替代 Codex、Claude Code、OpenCode，也不重新实现软件工程
Workflow。它位于 Coding Agent 与外部知识/执行环境之间，专门解决：

- 长任务上下文持续膨胀
- 多 Agent / 多 Session 上下文互相污染
- 不同角色共享过多无关信息
- Agent 切换后项目认知丢失
- 完整对话历史在 Agent 间重复复制
- 长期记忆、任务记忆、公共知识边界不清晰

AT Runtime 的核心问题只有一个：

> **当前 Agent 在当前任务阶段，应该看到什么，不应该看到什么。**

## 大框架（四层解耦）

```text
User
  → Coding Agent（Codex / Claude Code / OpenCode）—— 唯一主要交互入口
  → Superpowers（Workflow）—— 负责：怎么做
  → AT Runtime（Context & Memory Control Plane）—— 负责：知道什么
  → Execution（Local / Claude Squad / dmux）—— 负责：在哪里运行
  → Knowledge（OpenWiki）—— 负责：项目已经知道什么
```

## 六条核心原则

1. **Conversation is not Memory**——聊天历史不能直接成为长期记忆。
2. **Memory is scoped**——任何记忆都有 Scope。
3. **Context is constructed**——上下文每次动态构建，不直接继承。
4. **Agents communicate through artifacts**——Agent 之间通过 Handoff/Artifact
   通信，不复制完整 Conversation。
5. **Knowledge must be promoted**——长期知识必须经过验证和晋升。
6. **Everything is replaceable except the context protocol**——Codex、
   Superpowers、OpenWiki、Claude Squad 都可以替换；稳定的是
   **Task、Context、Memory、Scope、Handoff、Artifact、Session** 这些协议对象。

## AT Runtime 核心模块

```text
Session Registry   —— 谁正在执行什么任务，属于哪个 Scope
Context Router     —— 授权 + 相关性边界（允许看什么）
Context Assembler  —— 去重/排序/压缩/token budget，产出 Context Bundle
Memory Manager     —— Short / Medium / Long 三层 + Scope + 晋升
Policy Engine      —— 静态可解释规则（LLM 判断 relevance，Policy 判断 permission）
Handoff Manager    —— 结构化 Handoff（信息防火墙）
Knowledge Bridge   —— 统一知识查询接口（query/get/propose）
Runtime Observer   —— 机器可读事件与 token 估算
```

## 一次任务的数据流

```text
create_task
  → create_session(role, scope)
  → Policy Engine（授权边界）
  → Context Router（显式引用 + 默认最小集）
  → Context Assembler（预算/去重/provenance）
  → Context Bundle
  → ExecutionAdapter（spawn Codex）
  → collect output
  → Handoff Manager（结构化 handoff）
  → 下一 session / Memory Promotion / complete_session
```

## 目录结构

```text
project/
├── AGENTS.md
├── src/
├── tests/
├── docs/
└── .agent/
    ├── manifest.yaml
    ├── policies.yaml
    ├── runtime/    （sessions / tasks / events）
    ├── contexts/   （bundles / cache）
    ├── memory/     （short / medium / long）
    ├── handoffs/
    ├── artifacts/
    └── knowledge/  （refs）
```

## 版本路线

```text
V0.1   Codex + AT Runtime 核心（三 session 隔离 + 最小对比 eval）—— 当前
V0.2   接入 Superpowers（Workflow Stage → Context Policy）
V0.3   接入 OpenWiki（Knowledge Bridge）
V0.4   接入 Claude Squad / dmux + Git Worktree（并行执行）
V0.5   Benchmark（对比单长会话 / 全量共享 / AT 隔离）
```

## 快速开始（V0.1）

```powershell
python -m at_runtime init
at task start "<task>" --provider mock
at status
at context inspect <session-id>
at handoff inspect <handoff-id>
at eval
at doctor
```

实现计划见
`docs/superpowers/plans/2026-08-08-at-v2-context-runtime-mvp-implementation-plan.md`，
架构设计见
`docs/superpowers/specs/2026-08-08-at-v2-context-runtime-design.md`。

## 与 v1 的关系

v1（AT Flow）是"多 Agent 编排平台"，实战中编排开销大于产出。v2.0 在
`v2.0` 分支上重构为上下文隔离运行时，v1 代码完整保留在 git 历史中。

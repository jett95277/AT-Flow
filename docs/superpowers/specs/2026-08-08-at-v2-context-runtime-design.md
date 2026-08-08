# AT v2.0 Context Runtime Design

## Goal

v2.0 把 AT 从"多 Agent 编排平台"重构为**面向长任务与并行 Coding Agent 的
上下文隔离运行时**（Context & Memory Control Plane）。核心问题只有一个：

> 当前 Agent 在当前任务阶段，应该看到什么，不应该看到什么。

v2.0 不负责写代码、分析 Bug、选择工程方法、管理 Wiki 或 Worktree；
它只负责：**Context、Memory、Scope、Isolation、Handoff、Session、Provenance、
Budget**。

## 版本边界

v2.0 MVP（V0.1）拥有：

- 8 个核心模块的最小可用实现（Session Registry、Context Router、
  Context Assembler、Memory Manager、Policy Engine、Handoff Manager、
  Knowledge Bridge、Runtime Observer）。
- 三层记忆（Short / Medium / Long）+ Scope（Global/Project/Role/Feature/Task/
  Session）+ Promotion 管线 + Provenance。
- Structured Handoff（Agent 只通过 Handoff/Artifact 交换，不共享 Conversation）。
- Context Bundle（结构化上下文包，含 token budget）。
- ExecutionAdapter / KnowledgeAdapter 接口（V0.1 只实现 LocalAdapter，
  ClaudeSquad/dmux/OpenWiki 预留）。
- CLI（`at` 命令族），供 Codex 通过 AGENTS.md/Skills 调用。
- Python 3 + 文件系统存储（YAML/JSON/Markdown，`.agent/` 目录），不引入数据库。

v2.0 MVP 不拥有：

- Web Console / 云部署（v1 的 web/、deploy/ 不迁移）。
- Superpowers 深度集成（V0.2）、OpenWiki（V0.3）、Claude Squad/dmux（V0.4）、
  Benchmark（V0.5）——只预留接口。
- 多 Agent 并行执行（V0.1 是串行三 session 验证隔离）。
- 语言中英翻译链路（v1 的语言契约不再迁移）。

## 四层解耦

```text
Superpowers    → 怎么做（workflow）
AT Runtime     → 知道什么（context/memory control plane）
Execution      → 在哪里 / 怎么同时运行（Local / Claude Squad / dmux）
OpenWiki       → 项目已经知道什么（knowledge）
```

Codex、Superpowers、OpenWiki、Claude Squad 都是可替换 Adapter；稳定的是协议
对象：**Task、Context、Memory、Scope、Handoff、Artifact、Session**。

## 六条核心原则

1. **Conversation is not Memory**：聊天历史不能直接成为长期记忆。
2. **Memory is scoped**：任何记忆都有 Scope。
3. **Context is constructed**：上下文每次动态构建，不直接继承。
4. **Agents communicate through artifacts**：Agent 之间通过 Handoff/Artifact
   通信，不复制完整 Conversation。
5. **Knowledge must be promoted**：长期知识必须经过验证和晋升。
6. **Everything is replaceable except the context protocol**。

## 核心模块（V0.1 最小可用）

### 1. Session Registry

管理"谁正在执行什么任务，属于哪个 Context Scope"。字段：session_id、agent
(provider/role)、task(id/stage)、scope(project/branch/context_scope/
memory_scope)、parent、status。不保存完整 LLM 思维过程。

### 2. Context Router

最核心模块：根据 Agent/Task/Stage/Policy 决定"允许进入 Context Assembler 的
信息"。它是 **Authorization + Relevance Boundary**，不是 Retrieval Engine。

### 3. Context Assembler

决定"最终实际给模型什么"：去重、排序、压缩、token budget、provenance，
产出 Context Bundle。

### 4. Memory Manager

三层记忆 + Scope + 状态机（candidate/active/verified/deprecated/rejected）+
Promotion + GC。

### 5. Policy Engine

静态可解释规则（roles read/write 清单）。原则：**LLM 判断 relevance，
Policy 判断 permission**。

### 6. Handoff Manager

Structured Handoff（conclusion/evidence/constraints/unresolved/
recommended_actions/files/confidence）+ Lossless Reference 与 Compressed
Transfer 两种模式。

### 7. Knowledge Bridge

`query(topic)/get(ref)/propose(candidate)` 接口，适配 OpenWiki 或任意
Markdown 知识库。V0.1 实现为本地 `.agent/knowledge/` 引用层。

### 8. Runtime Observer

机器可读事件（session.created/context.injected/memory.promoted/
handoff.created/...），不做 Dashboard。

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
    ├── runtime/
    │   ├── sessions/
    │   ├── tasks/
    │   └── events/
    ├── contexts/
    │   ├── bundles/
    │   └── cache/
    ├── memory/
    │   ├── short/
    │   ├── medium/
    │   └── long/
    ├── handoffs/
    ├── artifacts/
    └── knowledge/
        └── refs/
```

## 数据模型

### Memory URI

```text
memory://project/<name>/long
memory://feature/<name>/medium
memory://task/<id>/medium
memory://role/<role>/long
memory://session/<id>/short
```

### Memory 三层

- **Short**：单 Session/Stage，高频变化，任务结束大量销毁。
- **Medium**：Task/Feature 周期，最重要；保存 root cause、约束、失败尝试、
  决策；role-specific view 受控共享。
- **Long**：跨任务、稳定、已验证、项目级；必须克制 + 晋升规则。

### Context Bundle

```yaml
context_bundle:
  id: CB-<task>-<role>-<seq>
  task: {id, goal}
  role: {type}
  constraints: [...]
  handoff: {from, summary}
  evidence: [{file, lines}]
  relevant_memory: [memory://...]
  knowledge: [wiki://...]
  expected_output: [...]
  token_budget: {max_context}
```

### Policy 示例

```yaml
roles:
  analysis: {read: [source, wiki, project_memory, analysis_memory],
             write: [short_memory, feature_memory, handoff:analysis_to_code]}
  code:     {read: [source, wiki, project_memory, code_memory, handoff:analysis_to_code],
             write: [source, short_memory, feature_memory, handoff:code_to_test]}
  test:     {read: [source, wiki, project_memory, test_memory, handoff:code_to_test],
             write: [test_artifacts, test_memory, handoff:test_to_code]}
```

## 核心 API（仅 7 个）

```text
create_task()
create_session()
build_context()
write_memory()
create_handoff()
complete_session()
promote_memory()
```

第一版不允许出现二三十个核心接口。

## CLI 边界

```text
at init
at status
at context inspect
at memory inspect
at task start
at handoff inspect
at spawn
at doctor
```

正常使用中用户不直接敲这些命令——Codex 通过 AGENTS.md/Skills 调用。

## MVP V0.1 验证门

用 Codex provider 跑通一个三 session 任务（analysis → handoff → code →
handoff → test），且满足：

1. 三个 Session 的 context（Context Bundle）互不共享。
2. 三个 Session 的 short memory 互不共享。
3. Task medium memory 可受控共享（role-specific view）。
4. Project long memory 可共享。
5. Agent 之间只通过 handoff 交换结果（无完整 conversation 复制）。
6. Runtime Observer 记录了 context.injected / handoff.created 等事件。
7. `at doctor` 与单元测试通过。

## 风险与 V0.1 务实决策（可用性优先）

### 风险 1：Context Router 的 relevance 判定

**决策：V0.1 不做 LLM 检索。** relevance 由三层静态机制决定：

1. **显式引用**：Task 创建时由调用方声明需要哪些 source/wiki/memory 引用，
   写入 Context Bundle 的 evidence / relevant_memory / knowledge 字段。
2. **Policy 静态规则**：角色的 read 清单决定 permission 边界。
3. **默认最小集**：Task 本身、Hard Constraints、Handoff 永远进入 Context，
   其余一律不自动注入。

一句话：V0.1 的 Context Router = 显式声明 + 静态授权，不引入检索不确定性与
额外 LLM 成本。检索能力留到后续版本。

### 风险 2：Execution 模型模糊

**决策：V0.1 采用进程级隔离。** 每个 Agent Session = LocalAdapter 启动一个
新的 Codex 进程调用，输入是组装好的 Context Bundle（prompt），输出是
Handoff/Artifact。Session 之间没有会话连续性，隔离是真实的；"Context is
constructed" 原则从第一版就落地。

代价（显式接受）：每次 session 需重新加载项目相关上下文；由显式引用机制
控制注入量，避免全量加载。

### 风险 3：验证时机太晚

**决策：V0.1 自带最小对比实验。** 验证门增加：

- Baseline：单个 Codex 长会话直接完成任务。
- AT 模式：analysis → code → test 三 session（只通过 handoff）。
- 同一 demo 任务，对比：Task Success、估算 Context tokens、Handoff
  Sufficiency（test 仅凭 handoff 是否能完成）。
- Runtime Observer 记录 `context.injected` 的 token 估算（按输入文本长度
  估算，不引入 tokenizer 依赖）。
- 提供 `at eval` 或等价脚本产出对比摘要。

V0.5 的完整 Benchmark 框架不做；V0.1 只做"能证明机制方向"的最小实验。

### 可用性优先原则（贯穿 V0.1）

- 8 个模块只做能跑通的最小实现；不做前瞻机制。
- Memory Promotion：V0.1 用手动/简单规则触发（`at memory promote`），不做
  自动提炼与完整 GC。
- 无 Context Priority Score 算法、无 Dashboard、无并行调度。
- 任何"机制"若没有在验证门中被使用，就不实现。

## 技术栈与存储

- Python 3.10+。
- 文件系统存储：YAML（manifest/policies）、JSON（context bundle/handoff/
  memory 元数据）、Markdown（memory 正文/artifact）。
- 无数据库、无 Web 框架、无网络依赖（Codex provider 通过现有 CLI 进程调用）。

## 与 v1 的关系

- 在 `v2.0` 分支上仓库内重写：删除 `src/at_flow/`、`web/`、`deploy/` 等 v1
  实现，替换为 `src/at_runtime/` 与 `at` CLI；v1 完整保留在 git 历史。
- 复用 v1 经验但不迁移代码：不做语言翻译、不做 Web/云、不做重型状态机。

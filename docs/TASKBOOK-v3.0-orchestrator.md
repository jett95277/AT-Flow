# xiaot v3.0 开发任务书 —— Coding Agent 上层任务编排平台

**版本**：v3.0（编排平台 MVP）
**状态**：设计收敛，待实施
**Spec 工作区**：`openspec/changes/v3-orchestrator-mvp/`（proposal/specs/design/tasks，演进中）
**对外口径**：复用开源 spec-driven 工作流（内部实现）；xiaot 定位为"agent 上层编排平台"

---

## 0. 定位（一句话）

> xiaot = **Coding Agent 上层的任务编排 CLI/平台**：像 spec 工具一样以 command+skill 注入 agent（项目级、启动即发现），用户 query 经 agent 先调 xiaot 编排，xiaot 返回"相关上下文片段"（JSON：指令+记忆摘要+路径引用），agent 据此执行；任务收口 xiaot 沉淀记忆（人工确认）——**带项目记忆开工、留新记忆收工**。

## 1. 主线（任务闭环 + 恢复）

```text
① agent 启动：项目 .opencode/ 中已注入 xiaot 编排 skill/command（部署写入 → 启动发现）
② 用户 query → agent 按指引调 xiaot
③ xiaot core 命令闭环：
      task     启动/恢复任务（建 .xiaot/workspace/<task-id>/）
      retrieve 注入任务相关记忆（medium/long 摘要，引用式）
      plan     产出并落盘规划指引（目标/步骤/文件/验收，完整文档）
      context  组装上下文片段（指令+记忆摘要+技能要点+规范路径）
      → agent 按片段执行（当前会话 agent，xiaot 不拉 headless）
④ agent 回报结果
⑤ settle    收工沉淀建议（提炼候选 → 人工确认 → medium/long）
⑥ checkpoint 关键节点打快照（workspace+记忆）；跨会话 task --resume 从 workspace 重建
```

## 2. 架构分层与关系

```text
用户 query（agent 会话）
  → xiaot 编排 CLI（被 agent 调用，JSON 机器面）
      ├── 记忆编排  经验账：medium{task专题,project项目} + long{global}
      ├── 技能编排  编排动作 skill（core5）→ 注入 agent；领域技能双入口
      ├── 规范编排  规范账：复用开源 spec-driven 工作流（判定→走 spec）
      └── 上下文构建 指令+摘要+路径引用 → agent
  → Coding Agent（opencode）执行（会话上下文 agent 自管）
  → xiaot 沉淀 → 记忆（人工确认）→ 下个任务
```

**xiaot 不管**：agent 会话上下文/压缩、执行进程拉起（headless 可选扩展）、代码状态（git）、规范引擎（复用）。

## 3. 记忆模型（A：裁 short 为 workspace）

| 层/区 | 承载 | 归属 scope |
|---|---|---|
| `.xiaot/workspace/<task-id>/` | 任务进行状态/产物/进度（在途，可丢弃）| 任务 |
| medium | 跨会话已验证结论（注入主源）| task(专题) / project(项目) |
| long | 跨项目稳定知识 | global |
| candidate | 收工提炼待确认中转 | 随提炼 |
| short（物理保留）| 兼容旧数据/技能 | 编排侧不再写 |

**时机**：开始/恢复注入一次（引用式）→ 中途按需 query → 收口 settle 建议 → **全部人工确认**入 medium/long；失败只提事实+未决；里程碑可提前出候选；冲突标记人工裁决；重复不重复入库（supersede 才更新）。

## 4. 技能层（对齐 spec 工具）

| 项 | 决策 |
|---|---|
| 编排动作 | core 5 skill/command：task/retrieve/plan/context/settle；`allowed-tools: Bash(xiaot:*)` |
| 注入 | **项目级** `.opencode/`（部署写入 → 启动发现）|
| 领域技能（13 个）| 双入口保留：编排路由 + 手动触发 |
| 能力本体 | xiaot CLI + 记忆引擎 + 规范工作流（skill 只是驱动）|

## 5. 模块与落点

```
lib/python/xiaot/            # 编排包（新增，与 xiaot_memory 并列）
├── models.py                # Task/Result/ContextPack/状态
├── workspace.py             # .xiaot/workspace/<task-id> 管理（plan/result/context）
├── memory_service.py        # 薄封装 xiaot_memory：retrieve(注入)/settle(建议/人工确认)
├── skill_router.py          # 领域技能路由 + 编排技能定义
├── spec_router.py           # 规范判定
├── spec_adapter.py          # 复用 spec-driven CLI（--json）
├── context_builder.py       # 上下文片段组装（指令+摘要+引用，引用式）
├── timeline.py              # checkpoint（workspace+记忆快照）/恢复
├── commands.py              # core5 命令实现（task/retrieve/plan/context/settle）
├── cli.py                   # xiaot CLI 入口（JSON 机器面）
└── __main__.py
bin/xiaot.ps1 / install 注入生成（.opencode/ skills+commands）
复用：xiaot_memory（memory_context/policy/settle/timeline）、13 领域技能
```

## 6. 核心接口与契约

- CLI 返回：JSON（机器可读），含 `{instruction, memory_summary[], skill_hint[], spec_path?, workspace, budget}` 等
- ContextPack（内部）：task/memory(摘要)/skills/spec/constraints/metadata
- Result（回报）：status{success,failed,cancelled,partial} + output/artifacts/metadata
- 恢复：`task --resume <task-id>` 读 workspace 重建

## 7. 里程碑（每步可交付 + 闭环测试）

| M | 内容 | 验证 |
|---|---|---|
| M1 | 编排包骨架 + models + workspace 基础 | import/构造/落盘测试 |
| M2 | memory_service 薄封装（retrieve/settle 建议+人工）| 检索/沉淀测试，83 旧测不回归 |
| M3 | context_builder（引用式片段组装 + 预算）| 组装/引用测试 |
| M4 | skill_router + 编排技能定义 | 路由 3 态测试 |
| M5 | spec_router + adapter（复用 spec CLI）| 判定/mock 测试 |
| M6 | commands + cli（core5 JSON 面）+ 注入生成 | CLI 冒烟 + 注入产物测试 |
| M7 | timeline 升级（workspace+记忆快照）+ resume | 快照/恢复测试 |
| M8 | 编排主线集成（task→retrieve→plan→context→(agent 回报)→settle）| 集成 + E2E + 回归全绿 |

## 8. 复用清单（不重写）

xiaot_memory 记忆引擎（memory_context/memory_policy/memory_settle/timeline）、13 领域技能、spec-driven 工作流（开源）、sync/doctor/tui 工具机制、bin 薄壳模式。

## 9. 验收标准（可答）

1. xiaot 是什么 → agent 上层编排 CLI/平台（带记忆开工、留记忆收工）
2. Coding Agent 是什么 → 执行者（当前会话，xiaot 注入 command+skill 驱动）
3. 记忆是什么 → 跨会话经验账（medium/long，workspace 管过程）
4. 技能层是什么 → 编排动作 driver（core5）+ 领域技能双入口
5. 规范是什么 → 可选分支（复用 spec 工作流，规范账）
6. xiaot 如何调 agent → 不拉起：编排产出上下文片段交当前 agent 执行
7. 上下文怎么协作 → 引用式注入（指令+摘要+路径），不干预 agent 压缩
8. 记忆何时进出 → 任务生命周期事件（开工注入/收工 settle/全人工确认）
9. 中断怎么恢复 → workspace 即恢复源
10. 如何演进 Harness → 三接口 + JSON 机器面扩展点

## 10. 边界（不做）

不重造 Coding Agent / 规范引擎 / Agent 会话压缩；不拉起 headless 执行（可选扩展）；不做 Web UI/多用户/分布式记忆；不迁移重写 xiaot_memory（薄封装）。

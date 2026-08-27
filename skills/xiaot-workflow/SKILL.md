---
name: 'xiaot-workflow'
description: '按 Superpowers 工作流执行完整任务。使用当用户说"开始任务 / 开工 / 走一遍流程"时。按任务复杂度分级执行：S 级直接干不写计划，M 级写轻量计划，L 级才走 Superpowers 完整计划流程（防止计划文档比代码多）。'
metadata:
  domain: 'workflow'
  source: 'manual'
---

执行（统一环境，无需手动 cd）。每一步先解析环境：

```powershell
# 小T 环境：XIAOT_HOME / MemoryCmd / ProjectRoot（~/.xiaot 由 sync-skills.ps1 部署）
. "$HOME\.xiaot\lib\xiaot-env.ps1"
Set-Location $Xiaot.ProjectRoot
```

## 0. 复杂度分级（先判定，再决定计划量）

| 级别 | 判定标准 | 计划量 |
|---|---|---|
| **S 小** | 单文件、单函数、≤30 行改动、零跨模块影响（修 typo、改名、调常量、加小函数） | **不写计划**，直接执行 |
| **M 中** | 多文件 / 新功能 / 集成点 / 重构（改 2-5 个文件） | **轻量计划**：一张 Markdown ≤50 行 |
| **L 大** | 跨模块、架构级、系统迁移、安全改造（影响面广） | **完整计划**：Superpowers writing-plans 全流程 |

不确定 S/M 时 → 选 M；不确定 M/L 时 → 选 L（少走弯路）。

## 1. 任务定义（所有级别都写）

```powershell
& $Xiaot.MemoryCmd memory add memory://task/<NNN>-<slug>/medium --conclusion "目标：…｜范围：…｜验收：…" [--constraint "<约束>"] --task <NNN>-<slug>
```

task-id 规则：`<3位序号>-<英文短横线>`（如 001-fix-beam），序号查 `xiaot-memory memory view`。

## 2. 按级别执行

### S 级（不写计划，直接干）
- 明确改动点 → 直接修改 → 跑相关测试 → 进步骤 4 沉淀
- 规则 12 依然有效：改动前口头说清"改什么、怎么改"等大哥点头

### M 级（轻量计划，一张 Markdown ≤50 行）
写 `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`，只含：
1. **背景**（2-3 行）
2. **方案**（改哪些文件、各自什么改动，列表）
3. **任务清单**（3-6 个任务项，一个 feature 一个 task，禁止按文件拆）
4. **验收标准**（可验证）

不给大哥看完整计划就动手（规则 12）。

### L 级（Superpowers 完整计划）
使用 writing-plans 技能全流程（插件内置；OpenCode 需自装）：
- 完整计划文档 + 任务分解
- 每个 task = 15-60 分钟工作量，简单无关任务合并

## 3. 任务分组规则（所有级别，借鉴 lite-plan 防文档膨胀）

1. **一个 feature = 一个 task**（即使涉及 3-5 个文件）
2. **禁止 file-per-task**（每个文件拆一个 task 是文档膨胀主因）
3. 简单无关任务合并，最小化 task 数量
4. 计划文档字数上限：S 级 0 行 / M 级 ≤50 行 / L 级 ≤200 行
5. 只有 L 级才允许引用 references/ 等大块资料

## 4. 阶段完成沉淀 + 打点（每个 Task 完成）

```powershell
# 沉淀当前阶段的 short（必须 --task）
& $Xiaot.MemoryCmd memory add memory://session/<阶段>-<task-id>/short --conclusion "<结论>" [--constraint "<约束>"] [--unresolved "<未决>"] --task <task-id>
# 打点
& $Xiaot.MemoryCmd memory checkpoint "<label>"
```

## 5. 完成收尾：settle -> 确认 -> 晋升

任务收尾时跑结算（默认 dry-run，不写盘），按五行分类逐条确认：

```powershell
& $Xiaot.MemoryCmd memory settle <task-id>
```

- **keep**：保留不动。
- **auto_archive**（纯过程记录）：确认后 `--apply` 自动归档。
- **suggest_promote**（已验证 + 有证据）：逐条确认后用严格动词晋升，需重提炼文本 + 证据：
  ```powershell
  & $Xiaot.MemoryCmd memory promote memory://session/<阶段>-<task-id>/short --to medium --confirmed --evidence "<证据，如 test:beam<2>" --distilled "<提炼后的结论，禁止复制原文>"
  ```
- **suggest_discard**（重复/无价值）：确认后丢弃：
  ```powershell
  & $Xiaot.MemoryCmd memory settle <task-id> --confirmed --discard <entry-id>
  ```
- **conflict_candidates**：确认后标记冲突：
  ```powershell
  & $Xiaot.MemoryCmd memory settle <task-id> --confirmed --conflict <entry-id>
  ```

确认全部完成后才执行 apply（settle 的 promote/discard/conflict 一律需用户确认，绝不自动）。

- 更新任务记忆（结论=交付内容，未决=遗留项），打点
- 若计划文档 > 代码量，主动说明原因（复杂度误判？分组没做？）

后续会话恢复：

```powershell
& $Xiaot.MemoryCmd memory get memory://task/<task-id>/medium
```

## Anti-Patterns

- **不要 S 级任务写完整计划**（文档 > 代码的直接原因，规则 12 的精神是"确认"不是"写文档"）
- 不要跳过复杂度分级直接开 writing-plans
- 不要按文件拆 task（一个文件一个 task = 文档膨胀）
- 不要在计划未经大哥确认时改代码
- 不要漏掉阶段沉淀或打点（规则 8：实时汇报进度）
- **不要用旧动词直接写正式记忆**（`memory write` 是 legacy 维护通道；新内容一律走 `memory add`）
- **不要自动执行 promote/discard/conflict**（settle 的 apply 只自动归档纯过程记录）
- 计划文档超限（M >50 / L >200 行）时不要硬撑，先压缩再继续

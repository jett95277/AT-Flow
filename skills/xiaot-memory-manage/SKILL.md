---
name: 'xiaot-memory-manage'
description: '三层记忆管理（AT 记忆整理）。使用当用户说"整理记忆 / 记忆整理 / 清理记忆 / 管理记忆"时。扫描 short/medium/long 三层，给出 promote/archive/discard 建议清单，逐条确认后批量执行，最后打点留痕。'
metadata:
  domain: 'memory'
  source: 'manual'
---

执行（统一环境，无需手动 cd）：

```powershell
# 小T 环境：XIAOT_HOME / ATCommand / ProjectRoot（~/.xiaot 由 sync-skills.ps1 部署）
. "$HOME\.xiaot\lib\xiaot-env.ps1"
Set-Location $Xiaot.ProjectRoot
```

## 流程（四步）

### 1. 扫描（全量拉出三层 + 每 task 结算建议）

```powershell
& $Xiaot.ATCommand memory stats
& $Xiaot.ATCommand memory view
# 对每个 task 跑结算（默认 dry-run，不写盘），聚合分类建议
& $Xiaot.ATCommand memory settle <task-id>
```

### 2. 分类建议（逐条给出动作 + 理由）

| 分类 | 建议动作 | 判断标准 |
|---|---|---|
| keep | 保留 | 仍活跃或不确定 |
| auto_archive | `settle --apply` 自动归档 | 纯过程记录（kind=process / 空内容） |
| suggest_promote | `promote --to medium --confirmed --evidence --distilled` | 已验证 + 有证据，形成决策/约束 |
| suggest_discard | `settle --confirmed --discard <id>` | 重复内容 / 确认无价值 |
| conflict_candidates | `settle --confirmed --conflict <id>` | 存在冲突待确认 |

输出建议清单（表格）：`URI | 当前状态 | 建议动作 | 理由`

### 3. 逐条确认后批量执行（绝不自动动记忆）

```powershell
# 提升（short → medium / medium → long）：严格动词，需确认 + 证据 + 重提炼
& $Xiaot.ATCommand memory promote memory://session/<id>/short --to medium --confirmed --evidence "<证据>" --distilled "<提炼文本>"
& $Xiaot.ATCommand memory promote memory://task/<id>/medium --to long --confirmed --evidence "<证据>" --distilled "<提炼文本>"

# 纯过程记录自动归档
& $Xiaot.ATCommand memory settle <task-id> --apply

# 弃用 / 冲突：确认后按 id 处理
& $Xiaot.ATCommand memory settle <task-id> --confirmed --discard <entry-id>
& $Xiaot.ATCommand memory settle <task-id> --confirmed --conflict <entry-id>
```

- 每执行一条就展示结果，等大哥点头再下一条
- 大哥说"批量执行"时才连续执行，否则逐条确认

### 4. 收尾打点留痕

```powershell
& $Xiaot.ATCommand memory checkpoint "memory-maintenance-<YYYYMMDD>"
```

汇报：`本次整理：提升 X 条、归档 Y 条、丢弃 Z 条，已打点`。

## 规则

- 只管理现有记忆，不写入新内容（写入走 xiaot-memo）
- promote 必须人工确认（记忆固化闸门，规则 12）
- discard 前必须展示该条完整内容，确认无价值才执行

## Anti-Patterns

- 不要自动批量 promote/discard（必须逐条确认）
- 不要动 active 状态记忆
- 不要把整理与新写入混在一个会话（规则 9）
- 不要跳过打点收尾（管理动作需留痕）

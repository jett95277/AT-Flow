---
name: 'at-memory-checkpoint'
description: '记录 AT 记忆时间线节点（打点）。使用当用户说"打点 / 记录时间节点 / 存个档 / checkpoint"或要求保存开发里程碑 / 时间节点时。触发 xiaot-memory memory checkpoint。'
metadata:
  domain: 'memory'
  source: 'manual'
---

执行（统一环境，无需手动 cd）：

```powershell
# 小T 环境：XIAOT_HOME / MemoryCmd / ProjectRoot（~/.xiaot 由 sync-skills.ps1 部署）
. "$HOME\.xiaot\lib\xiaot-env.ps1"
Set-Location $Xiaot.ProjectRoot
& $Xiaot.MemoryCmd memory checkpoint "<label>"
```

Label：从用户的里程碑提取简短标签（如 "fix beam stability"）。用户未给里程碑时，用当前阶段名。
把返回的 checkpoint JSON 展示给用户。

## Anti-Patterns

- 不要用含糊标签（如 "test"、"完成"），label 必须可回溯
- 任务未完成时不要打"完成"类标签
- 不要替大哥决定打点时机；他说"打点"才打

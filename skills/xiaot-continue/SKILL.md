---
name: 'xiaot-continue'
description: '恢复任务上下文。使用当用户说"继续某任务 / 切换某任务"（如"继续 V22"）。读取任务级记忆与时间线并展示摘要。'
metadata:
  domain: 'context-restore'
  source: 'manual'
---

执行（统一环境，无需手动 cd）：

```powershell
# 小T 环境：XIAOT_HOME / MemoryCmd / ProjectRoot（~/.xiaot 由 sync-skills.ps1 部署）
. "$HOME\.xiaot\lib\xiaot-env.ps1"
Set-Location $Xiaot.ProjectRoot
& $Xiaot.MemoryCmd memory get memory://task/<task-id>/medium
& $Xiaot.MemoryCmd memory timeline
```

## 切换回复格式（固定模板）

```
已切换到 **<task-id>** 专题。
- 目标：<conclusion 中的"目标"部分>
- 约束：<constraints>
- 未决：<unresolved>
- 最近进展：<timeline 最近 1-2 个节点 label + 时间>

大哥，待推进哪块？
```

## 规则

- 只关注当前专题（规则 9）
- 查询详情时按需读 `xiaot-memory memory get` 全量；摘要展示用上面的模板
- 若 conclusion 是模板句式（目标/范围/验收），按字段拆分展示；旧任务自由文本则直接展示

## Anti-Patterns

- 恢复上下文后不要立刻动手改代码；先等大哥指方向（规则 9）
- 不要同时恢复多个任务混在一个会话（规则 9：只关注当前专题）
- 不要跳过"问大哥待推进哪块"直接开干

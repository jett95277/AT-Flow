---
name: 'xiaot-memo'
description: '一句话记录到 AT 记忆。使用当用户说"记一下 / 记录 / 保存"并给出结论、约束或未决问题时。调用 xiaot-memory memory add 沉淀三字段。'
metadata:
  domain: 'memory'
  source: 'manual'
---

解析用户的话：

- 默认整句作为 conclusion
- 含"约束 / 限制 / 保持" → --constraint
- 含"待确认 / 未决 / 问题 / 风险" → --unresolved
- 任务归属：从对话上下文推断 task id；无法推断则不传 --task（short 会被拒绝，见下）

执行（统一环境，无需手动 cd）：

```powershell
# 小T 环境：XIAOT_HOME / MemoryCmd / ProjectRoot（~/.xiaot 由 sync-skills.ps1 部署）
. "$HOME\.xiaot\lib\xiaot-env.ps1"
Set-Location $Xiaot.ProjectRoot
```

short 准入规则：**必须绑定 task id**。推不出 task 时先跑 `& $Xiaot.MemoryCmd memory view` 查现有 task，仍无则明确告知大哥"无法确定 task，未记录"，绝不硬编：

```powershell
& $Xiaot.MemoryCmd memory add memory://session/<stage>-<task>/short --conclusion "<文本>" [--constraint "<约束>"] [--unresolved "<未决>"] --task <task-id>
```

session 名无法确定时用 `memory://session/<task>/short`。完成后告知已记录。

## 规则

- short 必须带 `--task`（准入规则，缺 task 会被拒绝：`[SHORT_REQUIRES_TASK]`）
- kind 默认 conclusion；纯观察用 `--kind observation`，风险用 `--kind risk`

## Anti-Patterns

- 不要把尚未验证的推测写成 conclusion（违反规则 11，须标 [推测]）
- 不要把敏感信息（密钥/凭据）写进记忆
- 无法推断 task id 时不要硬编一个；宁可不写并告知

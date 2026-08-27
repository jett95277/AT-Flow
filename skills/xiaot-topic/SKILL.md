---
name: 'xiaot-topic'
description: '创建 / 定义任务级记忆（专题）。使用当用户说"创建某专题 / 新任务 / 开始任务"。调用 xiaot-memory memory add 写入 task/medium。'
metadata:
  domain: 'memory'
  source: 'manual'
---

执行（统一环境，无需手动 cd）：

```powershell
# 小T 环境：XIAOT_HOME / MemoryCmd / ProjectRoot（~/.xiaot 由 sync-skills.ps1 部署）
. "$HOME\.xiaot\lib\xiaot-env.ps1"
Set-Location $Xiaot.ProjectRoot
```

## 创建流程（6 步）

1. **确定专题名**：用户给的名称 → 英文短横线 slug（如 "beam 稳定性修复" → `fix-beam`）

2. **确定序号**：运行 `xiaot-memory memory view`，从现有 task id 中找最大 `<NNN>-` 前缀序号，+1 生成 3 位序号（无则从 `001` 开始）：

```powershell
& $Xiaot.MemoryCmd memory view
```

3. **写入任务级记忆**（content 用模板句式，任务定义走 medium 准入例外）：

```powershell
& $Xiaot.MemoryCmd memory add memory://task/<NNN>-<slug>/medium --conclusion "目标：<一句话说清做什么>｜范围：<涉及的模块/文件/系统>｜验收：<可验证的完成标准>" [--constraint "<约束>"] [--unresolved "<未决>"] --task <NNN>-<slug>
```

4. **创建产出物目录 + README 索引**（issue-5：专题产出物统一归属与索引）：

```powershell
New-Item -ItemType Directory -Path "docs/<NNN>-<slug>" -Force | Out-Null
Set-Content -Path "docs/<NNN>-<slug>/README.md" -Value @"
# 专题 <NNN>-<slug>

- 目标：<conclusion 中的目标>
- 范围：<conclusion 中的范围>
- 验收：<conclusion 中的验收>
- 创建：<YYYY-MM-DD>

## 产出物清单

| 名称 | 类别 | 路径 | 状态 | 说明 |
|---|---|---|---|---|
| （首个产出物创建后登记） | design/test/report/assets | docs/<NNN>-<slug>/... | 进行中/完成 | ... |
"@ -Encoding UTF8
```

5. **汇报**：`已创建专题 <NNN>-<slug>`，展示序号 + conclusion 摘要 + 产出物索引路径

6. **产出物约定**：专题产出放入 `docs/<NNN>-<slug>/`（设计/测试/报告/资产），正式源码仍放项目 `src/`、`tests/`；每新增产出物登记到 README.md 清单

## 规则

- task-id = `<3位序号>-<英文短横线>`（如 `001-demo`、`008-fix-beam`）；旧任务（无序号）不迁移，新老并存
- conclusion 必须用模板句式：`目标：…｜范围：…｜验收：…`
- 无法确定序号时先跑 `xiaot-memory memory view`，不要凭记忆猜
- 产出物 README.md 必须创建（专题恢复时 `xiaot-continue` 可展示清单）

## Anti-Patterns

- 不要用中文或空格做 task id（必须短横线英文 + 序号前缀）
- 不要跳过序号查询直接写（会导致重号）
- 不要覆盖已有任务记忆而不先展示差异给大哥
- 目标含糊时不要硬造 conclusion；先问清任务目标

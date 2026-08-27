---
name: 'xiaot-status'
description: '查看 xiaot / AT 状态面板（记忆层、专题、时间线、skills 部署、健康检查）。使用当用户说"查看状态 / 状态 / tui / dashboard / 面板"时。运行 tui.ps1 输出状态。'
metadata:
  domain: 'status'
  source: 'manual'
---

执行（统一环境，无需手动 cd）：

```powershell
# 小T 环境：XIAOT_HOME / ATCommand / ProjectRoot（~/.xiaot 由 sync-skills.ps1 部署）
. "$HOME\.xiaot\lib\xiaot-env.ps1"
Set-Location $Xiaot.ProjectRoot
```

输出文本状态面板（适合对话内展示）：

```powershell
$tui = Join-Path $Xiaot.XIAOT_HOME 'bin\tui.ps1'
if (Get-Command pwsh -ErrorAction SilentlyContinue) {
  pwsh $tui -Mode text
} else {
  powershell.exe -ExecutionPolicy Bypass -File $tui -Mode text
}
```

把面板展示给大哥；如需交互式全屏面板，告知运行（无 pwsh 时用 powershell.exe -ExecutionPolicy Bypass 替换）：

```powershell
pwsh (Join-Path $Xiaot.XIAOT_HOME 'bin\tui.ps1')
```

## Anti-Patterns

- 不要用 `-Mode text` 之外的交互模式在对话内输出（交互模式会清屏等待按键，阻塞对话）
- 状态面板是只读视图，不要在查看时顺手改记忆

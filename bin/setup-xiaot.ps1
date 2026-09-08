# xiaot\setup-xiaot.ps1 — 一键部署编排 CLI（P0-1）
# 作用：把 xiaot\bin 加入用户 PATH（永久），自检 xiaot 可用。
# 用法：powershell -ExecutionPolicy Bypass -File xiaot\setup-xiaot.ps1
# 完成后新开终端执行 `xiaot init` 初始化项目。

$ErrorActionPreference = 'Stop'
$binDir = (Resolve-Path (Join-Path $PSScriptRoot 'bin')).Path

Write-Host "xiaot setup"
Write-Host "  1. 加入用户 PATH: $binDir"

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -and ($userPath -split ';') -contains $binDir) {
  Write-Host "     bin 已在 PATH（跳过）"
} else {
  $newPath = if ($userPath) { "$userPath;$binDir" } else { $binDir }
  [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
  Write-Host "     已加入（新终端生效）"
}

Write-Host "  2. 当前会话 PATH + 自检"
$env:PATH = "$binDir;" + $env:PATH
try {
  $out = & "$binDir\xiaot.cmd" --help 2>&1 | Select-Object -First 2
  Write-Host "     xiaot CLI 可用: $out"
} catch {
  Write-Host "     xiaot CLI 自检失败: $_"
  Write-Host "     请确认 python 在 PATH 且已 pip install pyyaml"
  exit 1
}

Write-Host "`n完成。新开终端后即可在任意项目："
Write-Host "  xiaot init                # 初始化当前项目（.xiaot + .opencode 注入）"
Write-Host "  xiaot task \"开发任务\" --project X   # 编排任务（带记忆开工）"
Write-Host "  xiaot settle / confirm    # 收工沉淀 / 人工确认写入"

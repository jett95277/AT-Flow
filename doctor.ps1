# xiaot\doctor.ps1 — 小T 路径诊断（v3.0：统一走 xiaot-env.ps1）
# 用法：powershell.exe -ExecutionPolicy Bypass -File xiaot\doctor.ps1（或 ~\.xiaot\bin\doctor.ps1）
# 展示：XIAOT_HOME(来源) / ATCommand(来源) / ProjectRoot(来源) / 配置优先级 / skills 部署 / at doctor
# 不再假定"xiaot 位于 AT-Flow 仓库下"，at 经 PATH / config 解析。

$ErrorActionPreference = 'Continue'

# ---------- 解析环境（优先脚本旁 lib，其次 ~/.xiaot）----------
$envScript = Join-Path $PSScriptRoot 'lib\xiaot-env.ps1'
if (-not (Test-Path $envScript)) { $envScript = Join-Path $env:USERPROFILE '.xiaot\lib\xiaot-env.ps1' }
if (Test-Path $envScript) { . $envScript } else {
  Write-Host "ERROR: xiaot-env.ps1 未找到（$envScript）。请先运行 sync-skills.ps1 初始化 ~/.xiaot" -ForegroundColor Red
  exit 1
}

Write-Host "===== xiaot doctor ====="
Write-Host ("XIAOT_HOME  : {0}  [{1}]" -f $Xiaot.XIAOT_HOME, $Xiaot.XIAOT_HOMESource)
Write-Host ("ATCommand   : {0}  [{1}]" -f $Xiaot.ATCommand, $Xiaot.ATCommandSource)
Write-Host ("ProjectRoot : {0}  [{1}]" -f $Xiaot.ProjectRoot, $Xiaot.ProjectRootSource)
Write-Host ("MEMORY_DIR  : {0}" -f (Join-Path $Xiaot.ProjectRoot '.agent'))
Write-Host ""
Write-Host "配置优先级：环境变量 AT_CMD -> 项目 .xiaot\config.json -> ~\.xiaot\config.json -> PATH"

# ---------- skills 部署状态 ----------
Write-Host ""
Write-Host "Skills 部署："
$src = Join-Path $Xiaot.XIAOT_HOME 'skills'
if (Test-Path $src) {
  $names = Get-ChildItem $src -Directory | Select-Object -ExpandProperty Name
  $hosts = @("$env:USERPROFILE\.codex\skills", "$env:USERPROFILE\.config\opencode\skills")
  foreach ($n in $names) {
    $deployed = ($hosts | Where-Object { Test-Path (Join-Path $_ $n) }).Count
    $mark = if ($deployed -eq 2) { 'OK' } elseif ($deployed -eq 1) { 'PD' } else { '--' }
    Write-Host ("  {0}  {1}  ({2}/2)" -f $mark, $n, $deployed)
  }
} else {
  Write-Host "  skills 快照缺失：$src（先运行 sync-skills.ps1）"
}

# ---------- at doctor ----------
if ($Xiaot.ATCommand -and (Test-Path $Xiaot.ATCommand)) {
  Write-Host ""
  Write-Host "at doctor："
  Push-Location
  Set-Location $Xiaot.ProjectRoot
  & $Xiaot.ATCommand doctor 2>$null
  Pop-Location
} else {
  Write-Host ""
  Write-Host "at doctor：跳过（AT 未找到）"
}

Write-Host ""
Write-Host "路径来源：AT 命令 = env AT_CMD -> 项目 .xiaot/config.json -> ~/.xiaot/config.json -> PATH"

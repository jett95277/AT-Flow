# xiaot\doctor.ps1 — 小T 路径诊断（v3.1 自包含）
# 用法：powershell.exe -ExecutionPolicy Bypass -File xiaot\doctor.ps1（或 ~\.xiaot\bin\doctor.ps1）
# 展示：XIAOT_HOME(来源) / ProjectRoot(来源) / python+PyYAML(来源) / 记忆命令 / skills 部署 / 记忆自检
# v3.1 起不再解析 at 二进制：记忆引擎内迁 xiaot_memory，doctor 做本机自检。

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
Write-Host ("ProjectRoot : {0}  [{1}]" -f $Xiaot.ProjectRoot, $Xiaot.ProjectRootSource)
Write-Host ("PythonExe   : {0}  [{1}]" -f $Xiaot.PythonExe, $Xiaot.PythonSource)
Write-Host ("MemoryCmd   : {0}" -f $Xiaot.MemoryCmd)
Write-Host ("MEMORY_DIR  : {0}" -f (Join-Path $Xiaot.ProjectRoot '.agent'))
Write-Host ""
Write-Host "记忆引擎：xiaot_memory（内迁，不依赖 at 二进制）；配置无 at_command"

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

# ---------- 记忆自检（本机，不依赖 at 二进制）----------
Write-Host ""
if (-not $Xiaot.PythonExe) {
  Write-Host "记忆自检：跳过（python 无 PyYAML）"
} else {
  $agentDir = Join-Path $Xiaot.ProjectRoot '.agent'
  if (-not (Test-Path $agentDir)) {
    Write-Host "记忆自检：.agent 不存在（$agentDir）——先跑 sync-skills.ps1 或 xiaot-memory init"
  } else {
    $stats = $null
    Push-Location
    Set-Location $Xiaot.ProjectRoot
    $env:PYTHONPATH = $Xiaot.PyModule
    $stats = & $Xiaot.PythonExe -m xiaot_memory memory stats 2>$null | ConvertFrom-Json
    Pop-Location
    if ($stats) {
      Write-Host ("记忆自检：OK  short={0} medium={1} long={2} total={3} checkpoints={4}" -f `
        $stats.tiers.short.total, $stats.tiers.medium.total, $stats.tiers.long.total, $stats.total, $stats.checkpoints)
    } else {
      Write-Host "记忆自检：失败（memory stats 无输出）"
    }
  }
}

Write-Host ""
Write-Host "环境：python = env XIAOT_PYTHON -> PATH python（需 PyYAML）；记忆引擎 = xiaot_memory"

# xiaot\lib\xiaot-env.ps1 — 小T 环境解析（定位层 B，v3.1 自包含）
#
# dot-source 后导出 $Xiaot（Hashtable）：
#   XIAOT_HOME   安装根：env XIAOT_HOME -> ~/.xiaot/config.json 的 xiaot_home -> ~/.xiaot
#   ProjectRoot  仓库根：cwd 向上找 .agent / .xiaot，找不到则用 cwd
#   PyModule     xiaot_memory 模块目录（本 lib\python，仓库与部署版同构）
#   PythonExe    带 PyYAML 的 python：env XIAOT_PYTHON -> PATH python（校验 import yaml）
#   MemoryCmd    薄记忆命令入口：本仓 bin\xiaot-memory.ps1（或部署版 ~/.xiaot\bin\xiaot-memory.ps1）
#   UserConfig   ~/.xiaot/config.json 路径
#
# 用途：skills / doctor.ps1 / tui.ps1 / bin\xiaot-memory.ps1 统一入口。
# v3.1 起小T 完全自包含：记忆引擎内迁 xiaot_memory，不再解析 at 二进制。

function Test-PythonWithYaml {
  param([string]$Exe)
  if (-not $Exe) { return $false }
  try {
    & $Exe -c "import yaml" 2>$null
    return ($LASTEXITCODE -eq 0)
  } catch { return $false }
}

function Get-XiaotEnv {
  # ---- ProjectRoot：cwd 向上找 .agent / .xiaot ----
  $p = (Get-Location).Path
  $root = $null
  $rootSource = 'cwd'
  while ($p) {
    if ((Test-Path (Join-Path $p '.agent')) -or (Test-Path (Join-Path $p '.xiaot'))) {
      $root = $p
      $rootSource = "向上找到 $p"
      break
    }
    $parent = Split-Path $p -Parent
    if ($parent -eq $p) { break }
    $p = $parent
  }
  if (-not $root) { $root = (Get-Location).Path; $rootSource = 'cwd（未找到 .agent/.xiaot）' }

  # ---- XIAOT_HOME ----
  # 注意：$HOME 是 PS 内置只读变量，这里用 $homeVal 避免同名冲突。
  $userConfig = Join-Path $env:USERPROFILE '.xiaot\config.json'
  $homeVal = $null
  $homeSource = '默认 ~/.xiaot'
  if ($env:XIAOT_HOME) { $homeVal = $env:XIAOT_HOME; $homeSource = '环境变量 XIAOT_HOME' }
  if (-not $homeVal -and (Test-Path $userConfig)) {
    try { $homeVal = (Get-Content $userConfig -Raw | ConvertFrom-Json).xiaot_home; if ($homeVal) { $homeSource = '~/.xiaot/config.json' } } catch { $homeVal = $null }
  }
  if (-not $homeVal) { $homeVal = Join-Path $env:USERPROFILE '.xiaot' }

  # ---- PyModule：本 env 脚本旁的 lib\python（仓库与部署版同构）----
  $pyModule = Join-Path $PSScriptRoot 'python'

  # ---- PythonExe：env XIAOT_PYTHON -> PATH python，校验 PyYAML ----
  $py = $null
  $pySource = 'PATH python'
  if ($env:XIAOT_PYTHON) { $py = $env:XIAOT_PYTHON; $pySource = '环境变量 XIAOT_PYTHON' }
  if (-not $py) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $py = $cmd.Source }
  }
  if ($py -and -not (Test-PythonWithYaml $py)) {
    $pySource = "$pySource（无 PyYAML，pip install pyyaml 后重试）"
    $py = $null
  }

  # ---- MemoryCmd：本仓/部署版 bin\xiaot-memory.ps1 ----
  $memoryCmd = Join-Path (Split-Path $PSScriptRoot -Parent) 'bin\xiaot-memory.ps1'
  if (-not (Test-Path $memoryCmd)) { $memoryCmd = $null }

  $global:Xiaot = @{
    XIAOT_HOME        = $homeVal
    XIAOT_HOMESource  = $homeSource
    ProjectRoot       = $root
    ProjectRootSource = $rootSource
    PyModule          = $pyModule
    PythonExe         = $py
    PythonSource      = $pySource
    MemoryCmd         = $memoryCmd
    UserConfig        = $userConfig
    ProjConfig        = Join-Path $root '.xiaot\config.json'
  }
  return $global:Xiaot
}

Get-XiaotEnv | Out-Null

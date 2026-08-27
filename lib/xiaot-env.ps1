# xiaot\lib\xiaot-env.ps1 — 小T 环境解析（定位层 B）
#
# dot-source 后导出 $Xiaot（Hashtable）：
#   XIAOT_HOME   安装根：env XIAOT_HOME -> ~/.xiaot/config.json 的 xiaot_home -> ~/.xiaot
#   ATCommand    at 命令：env AT_CMD -> 项目 .xiaot/config.json 的 at_command
#                            -> ~/.xiaot/config.json 的 at_command -> PATH
#   ProjectRoot  仓库根：cwd 向上找 .agent / .xiaot，找不到则用 cwd
#   UserConfig   ~/.xiaot/config.json 路径
#
# 用途：skills / doctor.ps1 / tui.ps1 / bin\at.ps1 统一入口，
# 消除 `.venv\Scripts\at.exe` 硬编码与"向上找 .agent"重复块。

function Resolve-AtCommand {
  param([string]$Value)
  if (-not $Value) { return $null }
  # 值是路径分隔符或 .exe 结尾 -> 视为路径
  if ($Value -match '[/\\]' -or $Value -like '*.exe') {
    if (Test-Path $Value) { return $Value }
    return $null
  }
  $cmd = Get-Command $Value -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  return $null
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

  # ---- ATCommand：env -> 项目 config -> 用户 config -> PATH ----
  $at = $null
  $atSource = 'PATH'
  if ($env:AT_CMD) { $at = $env:AT_CMD; $atSource = '环境变量 AT_CMD' }
  $projConfig = Join-Path $root '.xiaot\config.json'
  if (-not $at -and (Test-Path $projConfig)) {
    try { $at = (Get-Content $projConfig -Raw | ConvertFrom-Json).at_command; if ($at) { $atSource = '项目 .xiaot/config.json' } } catch { $at = $null }
  }
  if (-not $at -and (Test-Path $userConfig)) {
    try { $at = (Get-Content $userConfig -Raw | ConvertFrom-Json).at_command; if ($at) { $atSource = '~/.xiaot/config.json' } } catch { $at = $null }
  }
  $atResolved = Resolve-AtCommand $at
  if (-not $atResolved -and $at) {
    $atResolved = $at  # 保留原始值，供报错展示
    $atSource = "$atSource（未解析到可执行文件）"
  }
  if (-not $atResolved) {
    # PATH 兜底（排除 Windows 系统 at.exe 调度器误命中）
    $cmd = Get-Command at.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "$env:WINDIR\*") { $atResolved = $cmd.Source; $atSource = 'PATH' }
  }

  $global:Xiaot = @{
    XIAOT_HOME       = $homeVal
    XIAOT_HOMESource = $homeSource
    ATCommand        = $atResolved
    ATCommandSource  = $atSource
    ProjectRoot      = $root
    ProjectRootSource = $rootSource
    UserConfig       = $userConfig
    ProjConfig       = $projConfig
  }
  return $global:Xiaot
}

Get-XiaotEnv | Out-Null

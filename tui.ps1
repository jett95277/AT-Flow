# xiaot\tui.ps1 — xiaot 状态面板（TUI，v3.0：统一走 xiaot-env.ps1）
# 用法：
#   pwsh xiaot\tui.ps1               # 交互式全屏（r=刷新 q=退出）
#   pwsh xiaot\tui.ps1 -Mode text    # 文本面板（供 coding agent 对话内展示）
# 零依赖：PowerShell 7 + ANSI + at.exe JSON 输出

param(
  [ValidateSet('text', 'interactive')]
  [string]$Mode = 'interactive'
)

# ---------- 解析环境（优先脚本旁 lib，其次 ~/.xiaot）----------
$envScript = Join-Path $PSScriptRoot 'lib\xiaot-env.ps1'
if (-not (Test-Path $envScript)) { $envScript = Join-Path $env:USERPROFILE '.xiaot\lib\xiaot-env.ps1' }
if (Test-Path $envScript) { . $envScript } else {
  Write-Host "ERROR: xiaot-env.ps1 未找到（$envScript）。请先运行 sync-skills.ps1 初始化 ~/.xiaot" -ForegroundColor Red
  exit 1
}

$root = $Xiaot.ProjectRoot
$at = $Xiaot.ATCommand
if (-not $at) { Write-Host "ERROR: at 命令未找到（AT_CMD / ~/.xiaot/config.json / PATH）" -ForegroundColor Red; exit 1 }
# at.exe 以 cwd 定位 .agent，必须切换到仓库根
Set-Location $root
$xhome = $Xiaot.XIAOT_HOME
$skillsDir = Join-Path $xhome 'skills'

# ---------- ANSI ----------
$ESC = [char]27
$C = @{
  reset = "$ESC[0m"; bold = "$ESC[1m"; dim = "$ESC[2m"
  red = "$ESC[31m"; green = "$ESC[32m"; yellow = "$ESC[33m"
  blue = "$ESC[34m"; magenta = "$ESC[35m"; cyan = "$ESC[36m"
  white = "$ESC[37m"; bgdark = "$ESC[48;5;236m"
}

# ---------- 数据采集 ----------
function Get-Stats { try { & $at memory stats 2>$null | ConvertFrom-Json } catch { $null } }
function Get-Timeline { try { & $at memory timeline 2>$null | ConvertFrom-Json } catch { $null } }
function Get-Doctor { try { & $at doctor 2>$null | ConvertFrom-Json } catch { $null } }
function Get-TaskIds {
  $view = & $at memory view 2>$null
  $ids = @()
  if ($view) { $view | Select-String -Pattern 'task-([A-Za-z0-9\-]+)' -AllMatches | ForEach-Object { $_.Matches } | ForEach-Object { $ids += $_.Groups[1].Value } }
  $ids | Sort-Object -Unique
}

# ---------- 渲染：文本模式（对话内展示） ----------
function Show-Text {
  $stats = Get-Stats; $tl = Get-Timeline; $doc = Get-Doctor; $tasks = Get-TaskIds
  $skills = Get-ChildItem $skillsDir -Directory | Select-Object -ExpandProperty Name

  Write-Host ""
  Write-Host "===== xiaot 状态面板 ====="
  Write-Host "ProjectRoot : $root"
  if ($doc) { Write-Host ("健康    : {0}" -f $(if ($doc.ok) { 'OK' } else { '异常' })) }
  if ($stats) {
    Write-Host ("记忆    : short={0} medium={1} long={2} (total={3})" -f `
      $stats.tiers.short.total, $stats.tiers.medium.total, $stats.tiers.long.total, $stats.total)
    Write-Host ("时间线  : {0} 个 checkpoint" -f $stats.checkpoints)
  }
  if ($tasks) { Write-Host ("专题    : {0}" -f ($tasks -join ', ')) }
  Write-Host ("Skills  : {0} 个 -> {1}" -f $skills.Count, ($skills -join ', '))
  if ($tl) {
    Write-Host "最近节点:"
    $tl | Select-Object -First 3 | ForEach-Object {
      $ts = if ($_.created_at -is [datetime]) { $_.created_at.ToString('yyyy-MM-dd HH:mm') } else { $_.created_at.ToString() }
      Write-Host ("  - {0}  ({1})" -f $_.label, $ts)
    }
  }
  Write-Host "提示    : 交互式面板请运行 pwsh xiaot\tui.ps1"
  Write-Host ""
}

# ---------- 渲染：交互模式 ----------
function Show-Interactive {
  Clear-Host
  $stats = Get-Stats; $tl = Get-Timeline; $doc = Get-Doctor; $tasks = Get-TaskIds
  $skills = Get-ChildItem $skillsDir -Directory | Select-Object -ExpandProperty Name
  $hosts = @("$env:USERPROFILE\.codex\skills", "$env:USERPROFILE\.config\opencode\skills")

  Write-Host ("{0}{1}  xiaot 状态面板  {2}" -f $C.bgdark, $C.bold, $C.reset)
  Write-Host ("{0}{1}ProjectRoot:{2} {3}" -f $C.dim, $C.cyan, $C.reset, $root)
  Write-Host ""

  # 健康
  Write-Host ("{0}{1} 健康检查{2}" -f $C.bold, $C.green, $C.reset)
  if ($doc) {
    $doc.checks | ForEach-Object {
      $mark = if ($_.ok) { "$($C.green)✓$($C.reset)" } else { "$($C.red)✗$($C.reset)" }
      Write-Host ("  {0} {1}" -f $mark, $_.name)
    }
  }
  Write-Host ""

  # 记忆
  Write-Host ("{0}{1} 记忆层{2}" -f $C.bold, $C.blue, $C.reset)
  if ($stats) {
    foreach ($t in @('short', 'medium', 'long')) {
      $s = $stats.tiers.$t
      Write-Host ("  {0,-7} candidate={1} active={2} archived={3} deprecated={4}  total={5}" -f `
        $t, $s.candidate, $s.active, $s.archived, $s.deprecated, $s.total)
    }
    Write-Host ("  total={0}  checkpoints={1}" -f $stats.total, $stats.checkpoints)
  }
  Write-Host ""

  # 专题
  Write-Host ("{0}{1} 专题（{2}）{3}" -f $C.bold, $C.magenta, $tasks.Count, $C.reset)
  if ($tasks) { $tasks | ForEach-Object { Write-Host ("  {0}" -f $_) } } else { Write-Host "  (无)" }
  Write-Host ""

  # Skill + 宿主部署
  Write-Host ("{0}{1} Skills（{2}）{3}" -f $C.bold, $C.yellow, $skills.Count, $C.reset)
  foreach ($s in $skills) {
    $deployed = ($hosts | Where-Object { Test-Path (Join-Path $_ $s) }).Count
    $mark = if ($deployed -eq 2) { "$($C.green)●$($C.reset)" } elseif ($deployed -eq 1) { "$($C.yellow)◐$($C.reset)" } else { "$($C.red)○$($C.reset)" }
    Write-Host ("  {0} {1}  (部署 {2}/2)" -f $mark, $s, $deployed)
  }
  Write-Host ""

  # 时间线
  Write-Host ("{0}{1} 最近时间线{2}" -f $C.bold, $C.cyan, $C.reset)
  if ($tl) {
    $tl | Select-Object -First 5 | ForEach-Object {
      $ts = if ($_.created_at -is [datetime]) { $_.created_at.ToString('MM-dd HH:mm') } else { $_.created_at.ToString() }
      Write-Host ("  {0}  {1}" -f $ts, $_.label)
    }
  }
  Write-Host ""
  Write-Host ("{0}  [r] 刷新   [q] 退出{1}" -f $C.dim, $C.reset)
}

# ---------- 入口 ----------
if ($Mode -eq 'text') {
  Show-Text
} else {
  # 非交互环境（管道/CI）降级为一次性渲染
  $interactive = $false
  try { $interactive = [Console]::IsInputRedirected -eq $false } catch { $interactive = $false }
  if (-not $interactive) { Show-Text; exit 0 }

  Show-Interactive
  while ($true) {
    try {
      $key = [Console]::ReadKey($true)
      if ($key.Key -eq 'R') { Show-Interactive }
      elseif ($key.Key -eq 'Q') { break }
    } catch { Show-Text; break }
  }
}

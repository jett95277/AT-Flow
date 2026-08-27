# sync-skills.ps1 — 一键同步 xiaot\skills\* 到 Codex / OpenCode 宿主目录，
# 同时确保 ~/.xiaot 安装根（lib + bin + config.json）存在。
# 用法：pwsh xiaot\sync-skills.ps1（任意目录可运行；脚本内自定位源目录）
# skill 内容本身可移植（自动定位仓库根），同步为纯复制，无需路径替换。
#
# 孤儿清理保护：只清理"本次/上次由本脚本部署过"的 skill 目录（记录在目标目录
# .xiaot-skills-manifest.json），绝不删除宿主中其他来源的 skill（如 Codex 官方
# curated skills、插件安装的 skill）。

$ErrorActionPreference = 'Stop'

$src = Join-Path $PSScriptRoot 'skills'

# ---------- 安装根 ~/.xiaot（lib + bin + skills + config.json）----------
$homeRoot = Join-Path $env:USERPROFILE '.xiaot'
$homeLib = Join-Path $homeRoot 'lib'
$homeBin = Join-Path $homeRoot 'bin'
$homeSkills = Join-Path $homeRoot 'skills'
New-Item -ItemType Directory -Path $homeLib -Force | Out-Null
New-Item -ItemType Directory -Path $homeBin -Force | Out-Null
New-Item -ItemType Directory -Path $homeSkills -Force | Out-Null

$libSrc = Join-Path $PSScriptRoot 'lib\xiaot-env.ps1'
$binSrc = Join-Path $PSScriptRoot 'bin\at.ps1'
if (Test-Path $libSrc) { Copy-Item $libSrc (Join-Path $homeLib 'xiaot-env.ps1') -Force }
if (Test-Path $binSrc) { Copy-Item $binSrc (Join-Path $homeBin 'at.ps1') -Force }
foreach ($tool in @('doctor.ps1', 'tui.ps1')) {
  $toolSrc = Join-Path $PSScriptRoot $tool
  if (Test-Path $toolSrc) { Copy-Item $toolSrc (Join-Path $homeBin $tool) -Force }
}
# skills 快照：tui/doctor 的部署状态面板从 ~/.xiaot/skills 读取（稳定路径）
if (Test-Path $src) {
  if (Test-Path $homeSkills) { Remove-Item $homeSkills -Recurse -Force }
  Copy-Item $src $homeSkills -Recurse
}

# config.json 首次写入：自动探测 at_command（AT_CMD -> xiaot 父目录 venv -> PATH），后续不覆盖
$userConfig = Join-Path $homeRoot 'config.json'
if (-not (Test-Path $userConfig)) {
  $at = $env:AT_CMD
  if (-not $at) {
    $cand = Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\at.exe'
    if (Test-Path $cand) { $at = $cand }
  }
  if (-not $at) {
    $cmd = Get-Command at.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "$env:WINDIR\*") { $at = $cmd.Source }
  }
  @{ xiaot_home = ''; at_command = [string]$at; default_project = '' } |
    ConvertTo-Json | Set-Content $userConfig -Encoding UTF8
  Write-Host "created $userConfig (at_command=$at)"
}
$targets = @(
  (Join-Path $env:USERPROFILE '.codex\skills'),
  (Join-Path $env:USERPROFILE '.config\opencode\skills')
)

if (-not (Test-Path $src)) { throw "source not found: $src" }

$sourceNames = Get-ChildItem $src -Directory | Select-Object -ExpandProperty Name

foreach ($t in $targets) {
  if (-not (Test-Path $t)) { New-Item -ItemType Directory -Path $t -Force | Out-Null }

  # ---- 读取上次部署清单（不存在则为空）----
  $manifestPath = Join-Path $t '.xiaot-skills-manifest.json'
  $deployed = @()
  if (Test-Path $manifestPath) {
    try { $deployed = @((Get-Content $manifestPath -Raw | ConvertFrom-Json)) } catch { $deployed = @() }
  }

  # ---- 孤儿清理：只删"清单里有但源里已没有"的目录 ----
  $removed = @()
  foreach ($name in $deployed) {
    if ($sourceNames -notcontains $name) {
      $dir = Join-Path $t $name
      if (Test-Path $dir) { Remove-Item $dir -Recurse -Force; $removed += $dir }
    }
  }

  # ---- 同步源里所有 skill ----
  foreach ($name in $sourceNames) {
    $dst = Join-Path $t $name
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    Copy-Item (Join-Path $src $name) $dst -Recurse
  }

  # ---- 写回部署清单 ----
  $sourceNames | ConvertTo-Json | Set-Content $manifestPath -Encoding UTF8

  $removed | ForEach-Object { Write-Host "removed orphan (xiaot): $_" }
}

$count = $sourceNames.Count
Write-Host "Done. $count skills deployed to Codex + OpenCode (manifest protected)."

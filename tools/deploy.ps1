<#
.SYNOPSIS
  把 ChineseRim 模組檔案部署到 Mod Organizer 2 的 mods 資料夾（建議）或直接到 Skyrim Data（-Direct）。

.USAGE
  tools\deploy.ps1                 # → <MO2>\mods\ChineseRim\   （MO2 路徑取自 G:\AI\game\_tools\MO2）
  tools\deploy.ps1 -Direct         # → <Skyrim>\Data\           （沒有 MO2 時）
  tools\deploy.ps1 -Clean          # 先清空目標再複製

  部署內容：*.esm/*.esp（若已建立）、Scripts\*.pex、SKSE\Plugins\ChineseRim\*.json、
  SKSE\Plugins\ChineseRim.dll（若已建置）、Interface\ChineseRim\、ChineseRim_DISTR.ini、meshes/textures/sound。
#>
param(
  [switch]$Direct,
  [switch]$Clean,
  [string]$MO2Dir = "G:\AI\game\_tools\MO2"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$cfgPath = Join-Path $Root "tools\config.local.json"
$SkyrimDir = if (Test-Path $cfgPath) { (Get-Content $cfgPath -Raw | ConvertFrom-Json).skyrimDir } else { "H:\SteamLibrary\steamapps\common\Skyrim Special Edition" }

if ($Direct) { $Target = Join-Path $SkyrimDir "Data" }
else {
  if (-not (Test-Path $MO2Dir)) { throw "找不到 MO2：$MO2Dir（先跑 setup_dev.ps1，或改用 -Direct）" }
  $Target = Join-Path $MO2Dir "mods\ChineseRim"
}
Write-Host "[deploy] 目標：$Target"
if ($Clean -and -not $Direct -and (Test-Path $Target)) { Remove-Item $Target -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Target | Out-Null

# 先同步執行期 JSON
python (Join-Path $Root "tools\sync_skse.py") | Out-Null

$items = @(
  @{ src = "ChineseRim*.esm";  dst = "" },
  @{ src = "ChineseRim*.esp";  dst = "" },
  @{ src = "ChineseRim_DISTR.ini"; dst = "" },
  @{ src = "Scripts\*.pex";    dst = "Scripts" },
  @{ src = "SKSE\Plugins\ChineseRim\*"; dst = "SKSE\Plugins\ChineseRim" },
  @{ src = "dll\build\Release\ChineseRim.dll"; dst = "SKSE\Plugins" },
  @{ src = "Interface\ChineseRim\*"; dst = "Interface\ChineseRim" },
  @{ src = "meshes\*";  dst = "meshes" },
  @{ src = "textures\*"; dst = "textures" },
  @{ src = "sound\*";    dst = "sound" }
)
$n = 0
foreach ($it in $items) {
  $srcPath = Join-Path $Root $it.src
  $files = Get-ChildItem $srcPath -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "README.md" }
  if (-not $files) { continue }
  $dstDir = Join-Path $Target $it.dst
  New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
  $base = Split-Path (Join-Path $Root $it.src) -Parent
  foreach ($f in $files) {
    $rel = $f.FullName.Substring($base.Length).TrimStart('\')
    $to = Join-Path $dstDir $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $to -Parent) | Out-Null
    Copy-Item $f.FullName $to -Force
    $n++
  }
}
if (-not $Direct) {
  @"
[General]
modid=0
version=0.1.0
installationFile=
comments=凡人修仙傳 ChineseRim（開發部署）
"@ | Set-Content (Join-Path $Target "meta.ini") -Encoding UTF8
}
Write-Host "[deploy] 複製 $n 個檔案完成。"
if (-not $Direct) { Write-Host "[deploy] 在 MO2 左側啟用 ChineseRim，右側啟用 ChineseRim.esm 及各卷 .esp。" }

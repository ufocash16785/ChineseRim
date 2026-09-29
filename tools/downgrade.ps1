<#
.SYNOPSIS
  把 Skyrim SE 從 1.7.104（或任何版本）降級到 1.6.1170，並鎖住 Steam 自動更新。

.HOW
  透過 Steam 主控台 download_depot 從官方伺服器下載 1.6.1170 的三個 depot（Wildlander Wiki 記錄的 manifest），
  備份現有執行檔後覆蓋，最後刪除會導致舊版崩潰的 ContentCatalog.txt。

.USAGE
  以系統管理員開 PowerShell：
    Set-ExecutionPolicy -Scope Process Bypass -Force
    G:\AI\game\ChineseRim\tools\downgrade.ps1            # 完整流程（會開 Steam 主控台，指令逐條複製到剪貼簿）
    G:\AI\game\ChineseRim\tools\downgrade.ps1 -ApplyOnly # depot 已下載好，只做覆蓋
    G:\AI\game\ChineseRim\tools\downgrade.ps1 -Restore   # 還原 1.7.104 備份

  注意：Steam 主控台一次只能貼一條指令，等它印出 "Depot download complete" 再貼下一條。
#>
param(
  [switch]$ApplyOnly,
  [switch]$Restore,
  [string]$SkyrimDir = "H:\SteamLibrary\steamapps\common\Skyrim Special Edition"
)
$ErrorActionPreference = "Stop"
$TargetVersion = "1.6.1170.0"
$Depots = @(
  @{ id = 489831; manifest = "8442952117333549665"; expect = 16; desc = "Skyrim - Data (通用)" },
  @{ id = 489832; manifest = "8042843504692938467"; expect = 26; desc = "Skyrim - 英文語系" },
  @{ id = 489833; manifest = "1914580699073641964"; expect = 1;  desc = "SkyrimSE.exe 1.6.1170" }
)
function Say($m, $c = "Cyan") { Write-Host "[downgrade] $m" -ForegroundColor $c }
function ExeVersion($dir) { (Get-Item (Join-Path $dir "SkyrimSE.exe")).VersionInfo.FileVersion }

if (-not (Test-Path (Join-Path $SkyrimDir "SkyrimSE.exe"))) { throw "找不到 SkyrimSE.exe：$SkyrimDir" }
$steamPath = (Get-ItemProperty "HKCU:\Software\Valve\Steam" -ErrorAction SilentlyContinue).SteamPath
if (-not $steamPath) { $steamPath = "C:\Program Files (x86)\Steam" }
$steamPath = $steamPath -replace '/', '\'
$contentRoot = Join-Path $steamPath "steamapps\content\app_489830"
$backup = Join-Path $SkyrimDir "_backup_$(ExeVersion $SkyrimDir)"
$acf = Join-Path (Split-Path (Split-Path $SkyrimDir -Parent) -Parent) "appmanifest_489830.acf"

Say "Skyrim：$SkyrimDir（目前 $(ExeVersion $SkyrimDir)）"
Say "Steam：$steamPath"

# ---------------------------------------------------------------- 還原
if ($Restore) {
  $b = Get-ChildItem $SkyrimDir -Directory -Filter "_backup_*" | Sort-Object Name -Descending | Select-Object -First 1
  if (-not $b) { throw "沒有備份可還原" }
  Copy-Item (Join-Path $b.FullName "*") $SkyrimDir -Recurse -Force
  Say "已還原自 $($b.Name)，現在版本 $(ExeVersion $SkyrimDir)" Green
  exit 0
}

if ((ExeVersion $SkyrimDir) -eq $TargetVersion -and -not $ApplyOnly) { Say "已經是 $TargetVersion，無需降級" Green; exit 0 }

# ---------------------------------------------------------------- 1. 鎖自動更新
if (Test-Path $acf) {
  Set-ItemProperty $acf -Name IsReadOnly -Value $false
  $txt = Get-Content $acf -Raw
  $txt = $txt -replace '"AutoUpdateBehavior"\s+"\d"', '"AutoUpdateBehavior"		"1"'   # 1 = 只在啟動時更新
  Set-Content $acf $txt -NoNewline
  Set-ItemProperty $acf -Name IsReadOnly -Value $true
  Say "已鎖定 $acf（唯讀 + 只在啟動時更新）。之後請一律用 SKSE / MO2 啟動，不要從 Steam 直接啟動遊戲。" Yellow
} else { Say "找不到 appmanifest_489830.acf，請手動把它設為唯讀" Yellow }

# ---------------------------------------------------------------- 2. 下載 depot
if (-not $ApplyOnly) {
  Say "開啟 Steam 主控台。請依序在主控台執行下列三條指令（腳本會自動等待每個 depot 下載完成）。"
  Start-Process "steam://open/console"
  Start-Sleep 8
  foreach ($d in $Depots) {
    $cmd = "download_depot 489830 $($d.id) $($d.manifest)"
    try { Set-Clipboard $cmd } catch {}
    Say "[$($d.desc)] 請在 Steam 主控台執行：$cmd" Magenta
    $dir = Join-Path $contentRoot "depot_$($d.id)"
    # 非互動：輪詢直到 depot 資料夾出現、檔案數達標且 60 秒內大小不再變動（上限 30 分鐘）
    $deadline = (Get-Date).AddMinutes(30); $lastSize = -1; $stableSince = $null
    while ((Get-Date) -lt $deadline) {
      Start-Sleep 5
      if (-not (Test-Path $dir)) { continue }
      $files = Get-ChildItem $dir -Recurse -File -ErrorAction SilentlyContinue
      $size = ($files | Measure-Object Length -Sum).Sum
      if ($files.Count -ge $d.expect -and $size -eq $lastSize) {
        if (-not $stableSince) { $stableSince = Get-Date }
        elseif (((Get-Date) - $stableSince).TotalSeconds -ge 60) { break }
      } else { $stableSince = $null }
      $lastSize = $size
    }
    if (-not (Test-Path $dir)) { throw "30 分鐘內沒有看到 $dir，請確認指令已在 Steam 主控台執行" }
    $count = (Get-ChildItem $dir -Recurse -File).Count
    Say "  $dir：$count 個檔案（預期 $($d.expect)）" $(if ($count -ge $d.expect) { "Green" } else { "Yellow" })
  }
}

# ---------------------------------------------------------------- 3. 備份 + 覆蓋
foreach ($d in $Depots) { if (-not (Test-Path (Join-Path $contentRoot "depot_$($d.id)"))) { throw "缺少 depot_$($d.id)，請先下載" } }
Say "備份目前執行檔到 $backup ..."
New-Item -ItemType Directory -Force -Path $backup | Out-Null
foreach ($f in @("SkyrimSE.exe","SkyrimSELauncher.exe","bink2w64.dll","steam_api64.dll","Skyrim.ccc","Skyrim_Default.ini")) {
  $p = Join-Path $SkyrimDir $f; if (Test-Path $p) { Copy-Item $p $backup -Force }
}
Say "覆蓋 1.6.1170 檔案 ..."
foreach ($d in $Depots) {
  Copy-Item (Join-Path $contentRoot "depot_$($d.id)\*") $SkyrimDir -Recurse -Force
}
# 4. 清 ContentCatalog（新版格式會讓 1.6 崩潰）
$cc = Join-Path $env:LOCALAPPDATA "Skyrim Special Edition\ContentCatalog.txt"
if (Test-Path $cc) { Remove-Item $cc -Force; Say "已刪除 $cc" }

$now = ExeVersion $SkyrimDir
if ($now -eq $TargetVersion) {
  Say "完成：SkyrimSE.exe = $now" Green
  # 記錄
  $cfg = Join-Path (Split-Path $PSScriptRoot -Parent) "tools\config.local.json"
  @{ skyrimDir = $SkyrimDir; version = $now; backup = $backup; recordedAt = (Get-Date -f s) } | ConvertTo-Json | Set-Content $cfg -Encoding UTF8
  Say "接下來執行 tools\setup_dev.ps1（會安裝 SKSE 2.2.6 與其他工具）。"
} else {
  Say "版本仍為 $now，覆蓋可能失敗；可用 -Restore 還原" Red
}

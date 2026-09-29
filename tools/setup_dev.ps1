<#
.SYNOPSIS
  ChineseRim 開發環境一鍵安裝／檢查（Windows 10/11, PowerShell 5.1+）。

.USAGE
  以系統管理員身分開啟 PowerShell：
    Set-ExecutionPolicy -Scope Process Bypass -Force
    G:\AI\game\ChineseRim\tools\setup_dev.ps1              # 安裝缺少的工具並建置
    G:\AI\game\ChineseRim\tools\setup_dev.ps1 -CheckOnly   # 只檢查，不安裝
    G:\AI\game\ChineseRim\tools\setup_dev.ps1 -SkipBuild   # 安裝工具但不編譯

  會做的事：
    1. 找 Skyrim SE（Steam 489830）與 Creation Kit（Steam 1946180）；沒有就開 Steam 安裝頁
    2. winget 安裝 Git、Python 3.12、CMake、7-Zip、VS 2022 Build Tools（C++ 桌面工作負載）
    3. 下載 SKSE64（官方站）與 Mod Organizer 2（GitHub）到 G:\AI\game\_tools
    4. 準備 vcpkg（G:\AI\game\vcpkg）
    5. 編譯 Papyrus 腳本（需要 CK 的 PapyrusCompiler）與 ChineseRim.dll
    6. 列出必須手動從 Nexus 下載的相依模組
#>
[CmdletBinding()]
param(
  [switch]$CheckOnly,
  [switch]$SkipBuild,
  [string]$SkyrimDir = "H:\SteamLibrary\steamapps\common\Skyrim Special Edition",
  [string]$ToolsDir = "G:\AI\game\_tools",
  [string]$VcpkgDir = "G:\AI\game\vcpkg",
  [string]$SkseVersion = "2_02_06"   # 對應 Skyrim 1.6.1170；1.7.x 請改為 Nexus 上的 1.7 版本
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Log = Join-Path $ProjectRoot "tools\setup_dev.log"
function Say($msg, $color = "Cyan") { Write-Host "[ChineseRim] $msg" -ForegroundColor $color; Add-Content $Log "$(Get-Date -f s) $msg" }
function Ok($msg)   { Say "  OK  $msg" Green }
function Miss($msg) { Say "  --  $msg" Yellow }
function Fail($msg) { Say "  XX  $msg" Red }

Say "專案：$ProjectRoot"
Say "模式：$(if($CheckOnly){'只檢查'}else{'安裝'})"
New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

# ---------------------------------------------------------------------------
# 1. Skyrim SE / Creation Kit
# ---------------------------------------------------------------------------
function Get-SteamLibraries {
  $libs = @()
  $steamPath = (Get-ItemProperty "HKCU:\Software\Valve\Steam" -ErrorAction SilentlyContinue).SteamPath
  if (-not $steamPath) { $steamPath = "C:\Program Files (x86)\Steam" }
  $libs += $steamPath
  $vdf = Join-Path $steamPath "steamapps\libraryfolders.vdf"
  if (Test-Path $vdf) {
    Get-Content $vdf | Select-String '"path"\s+"([^"]+)"' | ForEach-Object { $libs += $_.Matches[0].Groups[1].Value -replace '\\\\','\' }
  }
  $libs | Select-Object -Unique
}
$CKExe = $null
if (-not (Test-Path (Join-Path $SkyrimDir "SkyrimSE.exe"))) {
  $SkyrimDir = $null
  foreach ($lib in Get-SteamLibraries) {
    $cand = Join-Path $lib "steamapps\common\Skyrim Special Edition"
    if (Test-Path (Join-Path $cand "SkyrimSE.exe")) { $SkyrimDir = $cand }
  }
}
if ($SkyrimDir) {
  Ok "Skyrim SE：$SkyrimDir"
  $ver = (Get-Item (Join-Path $SkyrimDir "SkyrimSE.exe")).VersionInfo.FileVersion
  Say "     版本 $ver"
  if ($ver -like "1.7.*") { Say "     1.7.x 執行檔：本專案以 1.6.1170 為開發目標，請先執行 tools\downgrade.ps1 降級。" Yellow }
  elseif ($ver -eq "1.6.1170.0") { Ok "版本 1.6.1170：SKSE 2.2.6 / Address Library / 全部相依模組皆有對應版本" }
  # 記錄給其他工具使用
  @{ skyrimDir = $SkyrimDir; version = $ver; recordedAt = (Get-Date -f s) } | ConvertTo-Json | Set-Content (Join-Path $ProjectRoot "tools\config.local.json") -Encoding UTF8
  if (Test-Path (Join-Path $SkyrimDir "CreationKit.exe")) { $CKExe = Join-Path $SkyrimDir "CreationKit.exe"; Ok "Creation Kit：$CKExe" }
  else { Miss "Creation Kit 未安裝"; if (-not $CheckOnly) { Start-Process "steam://install/1946180" } }
} else {
  Fail "找不到 Skyrim Special Edition。必須先在 Steam 購買並安裝（App 489830），Creation Kit（App 1946180）免費附帶。"
  if (-not $CheckOnly) { Start-Process "steam://install/489830" }
}

# ---------------------------------------------------------------------------
# 2. winget 工具
# ---------------------------------------------------------------------------
function Has-Cmd($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Winget-Install($id, $label, $override = $null) {
  if ($CheckOnly) { Miss "$label（未安裝）"; return }
  Say "安裝 $label ..."
  $args = @("install","--id",$id,"-e","--accept-source-agreements","--accept-package-agreements","--silent")
  if ($override) { $args += @("--override", $override) }
  & winget @args | Out-Null
}
if (-not (Has-Cmd winget)) { Fail "winget 不存在；請先從 Microsoft Store 安裝『應用程式安裝程式』"; }

if (Has-Cmd git)    { Ok "Git $((git --version) -replace 'git version ','')" } else { Winget-Install Git.Git "Git" }
if (Has-Cmd python) { Ok "Python $((python --version) -replace 'Python ','')" } else { Winget-Install Python.Python.3.12 "Python 3.12" }
if (Has-Cmd cmake)  { Ok "CMake $((cmake --version | Select-Object -First 1) -replace 'cmake version ','')" } else { Winget-Install Kitware.CMake "CMake" }
if (Test-Path "C:\Program Files\7-Zip\7z.exe") { Ok "7-Zip" } else { Winget-Install 7zip.7zip "7-Zip" }

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath = $null
if (Test-Path $vswhere) { $vsPath = & $vswhere -products * -version "[17.0,18.0)" -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath }
if ($vsPath) { Ok "Visual Studio C++ 工具：$vsPath" }
else { Winget-Install Microsoft.VisualStudio.2022.BuildTools "VS 2022 Build Tools (C++)" "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --add Microsoft.VisualStudio.Component.VC.CMake.Project" }

# ---------------------------------------------------------------------------
# 3. SKSE64 與 Mod Organizer 2
# ---------------------------------------------------------------------------
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$skseDir = Join-Path $ToolsDir "skse64"
if (Get-ChildItem $skseDir -Filter "skse64_loader.exe" -Recurse -ErrorAction SilentlyContinue) { Ok "SKSE64 已下載：$skseDir" }
elseif (-not $CheckOnly) {
  Say "下載 SKSE64 $SkseVersion（對應 Skyrim 1.6.1170）..."
  try {
    $link = "https://skse.silverlock.org/beta/skse64_$SkseVersion.7z"
    $zip = Join-Path $ToolsDir (Split-Path $link -Leaf)
    Invoke-WebRequest $link -OutFile $zip -UseBasicParsing
    & "C:\Program Files\7-Zip\7z.exe" x $zip "-o$skseDir" -y | Out-Null
    Ok "SKSE64：$skseDir（把 skse64_* 檔案與 Data 資料夾複製到 Skyrim 根目錄）"
  } catch { Fail "SKSE 下載失敗：$_ ；請手動到 https://skse.silverlock.org/ 下載" }
} else { Miss "SKSE64 未下載" }

$mo2Dir = Join-Path $ToolsDir "MO2"
if (Test-Path (Join-Path $mo2Dir "ModOrganizer.exe")) { Ok "Mod Organizer 2：$mo2Dir" }
elseif (-not $CheckOnly) {
  Say "下載 Mod Organizer 2（GitHub 最新版，可攜式 7z）..."
  try {
    $rel = Invoke-RestMethod "https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest"
    $asset = $rel.assets | Where-Object { $_.name -match '^Mod\.Organizer-[\d\.]+\.7z$' } | Select-Object -First 1
    $zip = Join-Path $ToolsDir $asset.name
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing
    & "C:\Program Files\7-Zip\7z.exe" x $zip "-o$mo2Dir" -y | Out-Null
    Ok "MO2：$mo2Dir（首次啟動選 Portable，遊戲指向 Skyrim SE）"
  } catch { Fail "MO2 下載失敗：$_ ；請手動到 https://github.com/ModOrganizer2/modorganizer/releases 下載" }
} else { Miss "Mod Organizer 2 未下載" }

# ---------------------------------------------------------------------------
# 4. vcpkg（CommonLibSSE-NG 需要）
# ---------------------------------------------------------------------------
if (Test-Path (Join-Path $VcpkgDir "vcpkg.exe")) { Ok "vcpkg：$VcpkgDir" }
elseif (-not $CheckOnly -and (Has-Cmd git)) {
  Say "安裝 vcpkg ..."
  git clone --depth 1 https://github.com/microsoft/vcpkg.git $VcpkgDir
  & (Join-Path $VcpkgDir "bootstrap-vcpkg.bat") -disableMetrics
  [Environment]::SetEnvironmentVariable("VCPKG_ROOT", $VcpkgDir, "User")
  $env:VCPKG_ROOT = $VcpkgDir
  Ok "vcpkg 完成，VCPKG_ROOT=$VcpkgDir"
} else { Miss "vcpkg 未安裝" }

# ---------------------------------------------------------------------------
# 5. 建置
# ---------------------------------------------------------------------------
if (-not $CheckOnly -and -not $SkipBuild) {
  Push-Location $ProjectRoot
  Say "驗證資料並同步 SKSE JSON ..."
  python tools\validate_data.py
  python tools\sync_skse.py

  # Papyrus
  $pc = if ($SkyrimDir) { Join-Path $SkyrimDir "Papyrus Compiler\PapyrusCompiler.exe" } else { $null }
  if ($pc -and (Test-Path $pc)) {
    $vanillaSrc = Join-Path $SkyrimDir "Data\Source\Scripts"
    if (-not (Test-Path $vanillaSrc) -and (Test-Path (Join-Path $SkyrimDir "Data\Scripts.zip"))) {
      Say "解壓原版 Papyrus 原始碼 Data\Scripts.zip ..."
      Expand-Archive (Join-Path $SkyrimDir "Data\Scripts.zip") (Join-Path $SkyrimDir "Data") -Force
    }
    $flags = Join-Path $vanillaSrc "TESV_Papyrus_Flags.flg"
    $skseSrc = Get-ChildItem $skseDir -Directory -Recurse -Filter "Source" -ErrorAction SilentlyContinue |
      Where-Object { $_.Parent.Name -eq "Scripts" } | Select-Object -First 1 -ExpandProperty FullName
    if (-not $skseSrc) { $skseSrc = Join-Path $skseDir "Data\Source\Scripts" }
    $depsSrc = Join-Path $ProjectRoot "Source\Deps"        # JContainers / PapyrusUtil / po3 的 .psc 放這裡
    New-Item -ItemType Directory -Force -Path $depsSrc, (Join-Path $ProjectRoot "Scripts") | Out-Null
    $imports = "$ProjectRoot\Source\Scripts;$depsSrc;$skseSrc;$vanillaSrc"
    Say "編譯 Papyrus ..."
    & $pc "$ProjectRoot\Source\Scripts" -all -f="$flags" -i="$imports" -o="$ProjectRoot\Scripts"
    if ($LASTEXITCODE -eq 0) { Ok "Papyrus 編譯完成 → Scripts\*.pex" } else { Fail "Papyrus 編譯有錯誤（多半是缺少 JContainers/PapyrusUtil/po3 的 .psc，請放到 Source\Deps）" }
  } else { Miss "略過 Papyrus 編譯：需要 Creation Kit 附帶的 PapyrusCompiler" }

  # DLL
  if ($vsPath -and (Test-Path (Join-Path $VcpkgDir "vcpkg.exe"))) {
    Say "建置 ChineseRim.dll（首次會由 vcpkg 編譯 CommonLibSSE-NG，約 10–20 分鐘）..."
    $env:VCPKG_VISUAL_STUDIO_PATH = $vsPath
    Push-Location (Join-Path $ProjectRoot "dll")
    cmake --preset vs2022-windows
    cmake --build build --config Release
    if ($LASTEXITCODE -eq 0) { Ok "DLL 建置完成 → dll\build\Release\ChineseRim.dll" } else { Fail "DLL 建置失敗，見上方輸出" }
    Pop-Location
  } else { Miss "略過 DLL 建置：需要 VS C++ 工具 + vcpkg" }
  Pop-Location
}

# ---------------------------------------------------------------------------
# 6. 需手動下載（Nexus 需登入）
# ---------------------------------------------------------------------------
Say ""
# 實際掃描 MO2 的 mods 資料夾（Portable 模式在 MO2 目錄下；Instance 模式在 %LOCALAPPDATA%\ModOrganizer\<instance>）
# 只列出真的沒偵測到的相依模組，而不是每次都印出整份清單。
$modDirs = @()
$portableMods = Join-Path $mo2Dir "mods"
if (Test-Path $portableMods) { $modDirs += $portableMods }
$instanceRoot = Join-Path $env:LOCALAPPDATA "ModOrganizer"
if (Test-Path $instanceRoot) {
  Get-ChildItem $instanceRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $m = Join-Path $_.FullName "mods"
    if (Test-Path $m) { $modDirs += $m }
  }
}
$installedNames = @()
foreach ($d in ($modDirs | Select-Object -Unique)) {
  $installedNames += (Get-ChildItem $d -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
}

$deps = @(
  @{ Name = "Address Library for SKSE Plugins";   Url = "https://www.nexusmods.com/skyrimspecialedition/mods/32444";  Keyword = "Address Library" },
  @{ Name = "SkyUI";                              Url = "https://www.nexusmods.com/skyrimspecialedition/mods/12604";  Keyword = "SkyUI" },
  @{ Name = "MCM Helper";                         Url = "https://www.nexusmods.com/skyrimspecialedition/mods/53000";  Keyword = "MCM Helper" },
  @{ Name = "JContainers SE";                     Url = "https://www.nexusmods.com/skyrimspecialedition/mods/16495";  Keyword = "JContainers" },
  @{ Name = "PapyrusUtil SE";                     Url = "https://www.nexusmods.com/skyrimspecialedition/mods/13048";  Keyword = "PapyrusUtil" },
  @{ Name = "powerofthree's Tweaks";              Url = "https://www.nexusmods.com/skyrimspecialedition/mods/51073";  Keyword = "powerofthree" },
  @{ Name = "Spell Perk Item Distributor (SPID)"; Url = "https://www.nexusmods.com/skyrimspecialedition/mods/36869";  Keyword = "Spell Perk Item Distributor" },
  @{ Name = "Keyword Item Distributor (KID)";     Url = "https://www.nexusmods.com/skyrimspecialedition/mods/55728";  Keyword = "Keyword Item Distributor" },
  @{ Name = "Open Animation Replacer (OAR)";      Url = "https://www.nexusmods.com/skyrimspecialedition/mods/92109";  Keyword = "Open Animation Replacer" },
  @{ Name = "Pandora Behaviour Engine";           Url = "https://www.nexusmods.com/skyrimspecialedition/mods/133232"; Keyword = "Pandora" },
  @{ Name = "Creation Kit Platform Extended";     Url = "https://www.nexusmods.com/skyrimspecialedition/mods/71371";  Keyword = "Platform Extended" },
  @{ Name = "SSEEdit (xEdit)";                    Url = "https://www.nexusmods.com/skyrimspecialedition/mods/164";    Keyword = "SSEEdit" }
)

$missing = $deps | Where-Object {
  $kw = $_.Keyword
  -not ($installedNames | Where-Object { $_ -like "*$kw*" })
}

if ($missing.Count -eq 0) {
  Ok "相依模組：MO2 mods 資料夾裡 12 個都偵測到了（Address Library/SkyUI/MCM Helper/JContainers/PapyrusUtil/po3 Tweaks/SPID/KID/OAR/Pandora/CKPE/SSEEdit）"
} else {
  Say "以下相依模組在 MO2 的 mods 資料夾裡沒偵測到，需登入 Nexus Mods 手動下載，再用 MO2 安裝：" Magenta
  $missing | ForEach-Object { Say ("   {0,-38} {1}" -f $_.Name, $_.Url) }
  Say "安裝後把 JContainers / PapyrusUtil / po3 的 .psc 原始碼複製到 Source\Deps\ 再重跑本腳本以編譯 Papyrus。"
}
if (-not $CheckOnly) { & (Join-Path $ProjectRoot "tools\make_shortcuts.ps1") -SkyrimDir $(if($SkyrimDir){$SkyrimDir}else{"H:\SteamLibrary\steamapps\common\Skyrim Special Edition"}) }
Say "完成。日誌：$Log"

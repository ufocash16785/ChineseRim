<# 在桌面建立正式 .lnk 捷徑（含 Skyrim 圖示）。setup_dev.ps1 結尾會自動呼叫；也可單獨執行。 #>
param([string]$SkyrimDir = "H:\SteamLibrary\steamapps\common\Skyrim Special Edition")
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$desktop = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
function Mk($name, $target, $cmdArgs, $icon, $desc) {
  $s = $ws.CreateShortcut((Join-Path $desktop "$name.lnk"))
  $s.TargetPath = $target; $s.Arguments = $cmdArgs; $s.WorkingDirectory = Split-Path $target -Parent
  if ($icon -and (Test-Path $icon)) { $s.IconLocation = "$icon,0" }
  $s.Description = $desc; $s.WindowStyle = 7; $s.Save()
  Write-Host "建立：$name.lnk → $target $cmdArgs"
}
$exe = Join-Path $SkyrimDir "SkyrimSE.exe"
Mk "凡人修仙傳" (Join-Path $Root "tools\launch.cmd") "" $exe "透過 MO2 / SKSE 啟動（不會觸發 Steam 更新）"
Mk "凡人修仙傳 - Creation Kit" (Join-Path $Root "tools\launch_ck.cmd") "" (Join-Path $SkyrimDir "CreationKit.exe") "開啟 Creation Kit"
$mo2 = "G:\AI\game\_tools\MO2\ModOrganizer.exe"
if (Test-Path $mo2) { Mk "Mod Organizer 2" $mo2 "" $mo2 "模組管理" }

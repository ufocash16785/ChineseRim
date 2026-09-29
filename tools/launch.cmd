@echo off
chcp 65001 >nul
rem 凡人修仙傳 ChineseRim 啟動器：優先 MO2，其次 SKSE；絕不直接啟動 SkyrimSE.exe / Steam（避免觸發自動更新）
setlocal
set "SKYRIM=H:\SteamLibrary\steamapps\common\Skyrim Special Edition"
set "MO2=G:\AI\game\_tools\MO2\ModOrganizer.exe"
set "MO2INSTANCE=Skyrim Special Edition"

if exist "%MO2%" (
  start "" "%MO2%" "moshortcut://%MO2INSTANCE%:SKSE"
  exit /b 0
)
if exist "%SKYRIM%\skse64_loader.exe" (
  cd /d "%SKYRIM%"
  start "" "%SKYRIM%\skse64_loader.exe"
  exit /b 0
)
echo.
echo [凡人修仙傳] 尚未安裝 SKSE 或 Mod Organizer 2。
echo 請先以系統管理員執行：G:\AI\game\ChineseRim\tools\setup_dev.ps1
echo （不要從 Steam 直接啟動遊戲，會升級回 1.7 版）
echo.
pause

@echo off
chcp 65001 >nul
rem Creation Kit 啟動器（有 MO2 時透過 MO2 啟動以看到模組檔案）
setlocal
set "SKYRIM=H:\SteamLibrary\steamapps\common\Skyrim Special Edition"
set "MO2=G:\AI\game\_tools\MO2\ModOrganizer.exe"
set "MO2=G:\AI\game\_tools\MO2\ModOrganizer.exe"
set "MO2INSTANCE=Skyrim Special Edition"
if exist "%MO2%" ( start "" "%MO2%" "moshortcut://%MO2INSTANCE%:Creation Kit" & exit /b 0 )
echo Creation Kit 尚未安裝：請在 Steam 安裝 App 1946180。
start "" "steam://install/1946180"
pause

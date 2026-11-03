@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --name FlightSimCarreira --collect-all webview --collect-all SimConnect --add-data "aerocarreira/midnight;aerocarreira/midnight" --add-data "in_game;in_game" launch_midnight.py
if errorlevel 1 exit /b 1
echo Aplicativo em dist\FlightSimCarreira\FlightSimCarreira.exe

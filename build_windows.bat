@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" scripts\fetch_maplibre.py
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" scripts\prepare_app_icon.py
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --icon "assets/flight_sim_carreira.ico" --noconfirm --clean --noupx --onedir --name FlightSimCarreira --collect-all webview --collect-all pythonnet --collect-all clr_loader --collect-all cffi --hidden-import clr --collect-all SimConnect --add-data "aerocarreira/midnight;aerocarreira/midnight" --add-data "in_game;in_game" launch_midnight.py
if errorlevel 1 exit /b 1
echo Aplicativo em dist\FlightSimCarreira\FlightSimCarreira.exe

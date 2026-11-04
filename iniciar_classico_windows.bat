@echo off
cd /d "%~dp0"
set FLIGHTSIM_CLASSIC=1
".venv\Scripts\python.exe" -m aerocarreira
pause

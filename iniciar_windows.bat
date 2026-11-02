@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m aerocarreira
) else (
  py -3.11 -m aerocarreira
)
if errorlevel 1 pause

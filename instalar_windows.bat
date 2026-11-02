@echo off
cd /d "%~dp0"
py -3.11 -m venv .venv
if errorlevel 1 (echo Falha. Confirme Python 3.11 x64 instalado.& pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements-windows.txt
if errorlevel 1 (echo Falha ao instalar adaptador SimConnect. Modo demo continua disponivel.& pause & exit /b 1)
echo Instalacao finalizada. Execute iniciar_windows.bat
pause

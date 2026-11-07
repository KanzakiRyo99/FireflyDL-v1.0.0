@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" app.py
    exit /b 0
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
    if errorlevel 1 pause
    exit /b 0
)

where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw app.py
    exit /b 0
)
python app.py
if errorlevel 1 pause

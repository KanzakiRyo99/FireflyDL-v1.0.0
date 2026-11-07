@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" cli.py %*
) else (
    python cli.py %*
)
if errorlevel 1 (
    echo.
    echo 命令退出码：%errorlevel%
)
if "%~1"=="" pause

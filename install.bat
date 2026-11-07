@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   FireflyDL 环境安装
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没有找到 python，请先安装 Python 3.10+ 并勾选 Add to PATH。
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] 创建虚拟环境 .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
) else (
    echo [1/3] 已存在虚拟环境 .venv。
)

echo [2/3] 安装 / 更新依赖 ...
".venv\Scripts\python.exe" -m pip install -U pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络或代理。
    pause
    exit /b 1
)

echo [3/3] 检查 ffmpeg ...
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [提示] 未在 PATH 中找到 ffmpeg。高画质音视频合并、MP3 转换需要它。
    echo        可安装到 C:\ffmpeg\bin，或在应用「设置 - 工具与维护」中指定路径。
) else (
    echo [OK] 已找到 ffmpeg。
)

echo.
echo ============================================
echo   安装完成！双击 start_gui.bat 启动界面
echo   命令行：start_cli.bat --help
echo ============================================
pause

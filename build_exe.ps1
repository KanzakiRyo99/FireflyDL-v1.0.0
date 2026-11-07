# FireflyDL Windows 打包脚本
# 用法：powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
# 输出：dist\FireflyDL\FireflyDL.exe（GUI）与 dist\FireflyDL-CLI\FireflyDL-CLI.exe

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

Write-Host '=== FireflyDL 打包 ===' -ForegroundColor Cyan

# 优先使用已装好依赖的 .venv；如果 .venv 还没装依赖，则回退到系统 Python。
$python = 'python'
if (Test-Path '.venv\Scripts\python.exe') {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $probe = & '.venv\Scripts\python.exe' -c "import PyInstaller, yt_dlp, PIL, mutagen; print('ok')" 2>$null
    $probeCode = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($probeCode -eq 0 -and "$probe" -match 'ok') {
        $python = '.venv\Scripts\python.exe'
    }
}
Write-Host "使用 Python：$python"

& $python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '安装 PyInstaller ...'
    & $python -m pip install -U pyinstaller
}

if (-not (Test-Path 'assets\firefly.ico')) {
    throw '缺少 assets\firefly.ico'
}

$common = @(
    '--noconfirm', '--clean',
    '--collect-all', 'yt_dlp',
    '--add-data', 'assets;assets',
    '--add-data', 'yt_dlp_plugins;yt_dlp_plugins',
    '--hidden-import', 'mutagen',
    '--hidden-import', 'PIL._tkinter_finder',
    '--manifest', 'assets\app.manifest'
)

Write-Host '构建 GUI ...'
& $python -m PyInstaller @common --windowed --name FireflyDL --icon 'assets\firefly.ico' app.py
if ($LASTEXITCODE -ne 0) { throw 'GUI 打包失败' }

Write-Host '构建 CLI ...'
& $python -m PyInstaller @common --console --name FireflyDL-CLI cli.py
if ($LASTEXITCODE -ne 0) { throw 'CLI 打包失败' }

Write-Host ''
Write-Host '完成：' -ForegroundColor Green
Write-Host '  dist\FireflyDL\FireflyDL.exe'
Write-Host '  dist\FireflyDL-CLI\FireflyDL-CLI.exe'
Write-Host ''
Write-Host '提示：exe 体积较大是因为内置 yt-dlp 全部提取器；首次启动会稍慢。'
Write-Host '若打包后快手解析失效，请确认打包目录内存在 yt_dlp_plugins 文件夹。'

# WeWrite 依赖安装脚本 (Windows PowerShell 版本)
# 用法：powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$PYTHON = "python"
if ($env:PYTHON) { $PYTHON = $env:PYTHON }

if (-not (Get-Command $PYTHON -ErrorAction SilentlyContinue)) {
    Write-Host "找不到 $PYTHON，请先安装 Python 3.11+" -ForegroundColor Red
    exit 1
}

$pythonVersion = & $PYTHON --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "无法获取 Python 版本" -ForegroundColor Red
    exit 1
}

$versionMatch = [regex]::Match($pythonVersion, "Python (\d+)\.(\d+)")
if ($versionMatch.Success) {
    $major = [int]$versionMatch.Groups[1].Value
    $minor = [int]$versionMatch.Groups[2].Value
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
        Write-Host "Python 版本过低：$pythonVersion，需要 Python 3.11+" -ForegroundColor Red
        exit 1
    }
}

if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境 .venv ..." -ForegroundColor Cyan
    & $PYTHON -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "创建虚拟环境失败" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "复用已有的 .venv" -ForegroundColor Cyan
}

Write-Host "安装依赖到 .venv ..." -ForegroundColor Cyan
$venvPython = ".venv\Scripts\python.exe"

& $venvPython -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "升级 pip 失败" -ForegroundColor Red
    exit 1
}

& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "安装依赖失败" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "完成！依赖已装入 $PWD\.venv" -ForegroundColor Green
Write-Host "无需手动 activate，skill 运行时会自动使用 .venv\Scripts\python.exe" -ForegroundColor Green

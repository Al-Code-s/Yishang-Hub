# 意尚智造集成平台 —— 本地后端开发启动脚本
# 用法： powershell -ExecutionPolicy Bypass -File scripts\dev_backend.ps1 [-Port 8000]
# 说明：开发使用 backend/.venv；生产请使用 Gunicorn（见 docs/deployment.md）。
param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repoRoot 'backend'
$python = Join-Path $backend '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "未找到虚拟环境：$python。请先在 backend 目录创建 .venv 并安装依赖。"
}

$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $backend

Write-Host '[1/4] django check ...'
& $python manage.py check

Write-Host '[2/4] 迁移状态检查（不自动生成迁移）...'
& $python manage.py makemigrations --check --dry-run

Write-Host '[3/4] 应用迁移 ...'
& $python manage.py migrate

Write-Host "[4/4] 启动开发服务器 http://127.0.0.1:$Port ..."
Write-Host '      生产环境禁止使用 runserver 对外提供服务。'
& $python manage.py runserver "127.0.0.1:$Port"
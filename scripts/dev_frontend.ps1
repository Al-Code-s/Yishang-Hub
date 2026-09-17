# 意尚智造集成平台 —— 本地前端开发启动脚本
# 用法： powershell -ExecutionPolicy Bypass -File scripts\dev_frontend.ps1 [-BackendPort 8000] [-Port 5173]
param(
    [int]$BackendPort = 8000,
    [int]$Port = 5173
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $repoRoot 'frontend'

# npm 缓存放到仓库内的临时目录，避免污染用户目录
$env:npm_config_cache = Join-Path $repoRoot '.tmp\npm-cache'
$env:VITE_DEV_BACKEND = "http://127.0.0.1:$BackendPort"

Set-Location -LiteralPath $frontend

if (-not (Test-Path -LiteralPath (Join-Path $frontend 'node_modules'))) {
    Write-Host '未找到 node_modules，正在安装依赖 ...'
    npm install
}

Write-Host "启动前端开发服务器 http://127.0.0.1:$Port （代理 /api -> $env:VITE_DEV_BACKEND）"
npm run dev -- --port $Port
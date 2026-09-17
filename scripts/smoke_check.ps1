# 意尚智造集成平台 —— 本地冒烟检查脚本
# 一次性执行后端与前端的主要检查项，输出真实结果，不做任何"假定通过"。
# 用法： powershell -ExecutionPolicy Bypass -File scripts\smoke_check.ps1
$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repoRoot 'backend'
$frontend = Join-Path $repoRoot 'frontend'
$python = Join-Path $backend '.venv\Scripts\python.exe'

$env:PYTHONIOENCODING = 'utf-8'
$env:npm_config_cache = Join-Path $repoRoot '.tmp\npm-cache'

$failed = @()

function Step([string]$name, [scriptblock]$action) {
    Write-Host ""
    Write-Host "=== $name ===" -ForegroundColor Cyan
    & $action
    if ($LASTEXITCODE -ne 0) {
        Write-Host "!! $name 失败（退出码 $LASTEXITCODE）" -ForegroundColor Red
        $script:failed += $name
    }
}

Push-Location -LiteralPath $backend
Step 'django check' { & $python manage.py check }
Step 'makemigrations --check（应无变更）' { & $python manage.py makemigrations --check --dry-run }
Step 'ruff check' { & $python -m ruff check apps config tests }
Step 'pytest' { & $python -m pytest tests -q --reuse-db }
Pop-Location

Push-Location -LiteralPath $frontend
Step 'vue-tsc 类型检查' { npm run typecheck }
Step 'vitest' { npm run test }
Step 'vite build' { npm run build }
Pop-Location

Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host '全部检查通过。' -ForegroundColor Green
} else {
    Write-Host ("以下检查失败：" + ($failed -join '、')) -ForegroundColor Red
    exit 1
}
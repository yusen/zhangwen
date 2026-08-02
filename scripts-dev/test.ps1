# 掌问全量测试脚本
# 用法：在仓库根目录运行 .\scripts-dev\test.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python virtual environment not found. Run: py -3.13 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r services\local-api\requirements.txt"
}

Write-Host "=== 掌问全量测试 ===" -ForegroundColor Cyan

# 1. Contracts 构建与类型检查
Write-Host "`n[1/4] 契约包构建与类型检查..." -ForegroundColor Yellow
Push-Location "$root\packages\contracts"
pnpm build
pnpm typecheck
Pop-Location
Write-Host "  契约包构建与类型检查通过" -ForegroundColor Green

# 2. 前端类型检查
Write-Host "`n[2/4] 前端类型检查..." -ForegroundColor Yellow
Push-Location "$root\apps\desktop"
pnpm typecheck
Pop-Location
Write-Host "  前端类型检查通过" -ForegroundColor Green

# 3. 前端测试
Write-Host "`n[3/4] 前端单元测试..." -ForegroundColor Yellow
Push-Location "$root\apps\desktop"
pnpm test
Pop-Location
Write-Host "  前端测试通过" -ForegroundColor Green

# 4. Python 测试
Write-Host "`n[4/4] Python Sidecar 测试..." -ForegroundColor Yellow
Push-Location "$root\services\local-api"
& $python -m pytest tests/ -v
Pop-Location
Write-Host "  Python 测试通过" -ForegroundColor Green

Write-Host "`n=== 所有测试通过 ===" -ForegroundColor Green

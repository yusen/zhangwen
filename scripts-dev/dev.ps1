# 掌问开发环境一键启动脚本
# 用法：在仓库根目录运行 .\scripts-dev\dev.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python virtual environment not found. Run: py -3.13 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r services\local-api\requirements.txt"
}

Write-Host "=== 掌问开发环境启动 ===" -ForegroundColor Cyan

# 1. 构建 contracts
Write-Host "`n[1/3] 构建共享契约包..." -ForegroundColor Yellow
Push-Location "$root\packages\contracts"
pnpm build
Pop-Location

# 2. 启动 Python sidecar
Write-Host "`n[2/3] 启动 Python Sidecar (端口 8100)..." -ForegroundColor Yellow
$apiJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location "$root\services\local-api"
    & "$root\.venv\Scripts\python.exe" -m uvicorn zhangwen.main:app --reload --port 8100 --host 127.0.0.1
} -ArgumentList $root

# 3. 启动前端开发服务器
Write-Host "[3/3] 启动前端开发服务器 (端口 5173)..." -ForegroundColor Yellow
Push-Location "$root\apps\desktop"
Write-Host "`n=== 启动完成 ===" -ForegroundColor Green
Write-Host "  Python Sidecar: http://127.0.0.1:8100/api/health" -ForegroundColor Gray
Write-Host "  前端开发服务器: http://localhost:5173" -ForegroundColor Gray
Write-Host "`n按 Ctrl+C 停止所有服务。" -ForegroundColor Gray
pnpm dev
Pop-Location

# 清理
Stop-Job $apiJob
Remove-Job $apiJob
Write-Host "`n已停止所有服务。" -ForegroundColor Yellow

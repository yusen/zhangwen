# Zhangwen Web Development Mode launcher.
# Starts the existing FastAPI Sidecar and React app without starting Tauri/Rust.
# This is the default interaction-validation entry for the unified project conversation.

param(
    [switch]$FakeProvider,
    [switch]$PaidProvider
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$jobs = @()

function Invoke-Pnpm {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    $pnpm = Get-Command "pnpm" -ErrorAction SilentlyContinue
    if ($pnpm) {
        & $pnpm.Source @Arguments
        return
    }
    $corepack = Get-Command "corepack" -ErrorAction SilentlyContinue
    if ($corepack) {
        & $corepack.Source pnpm @Arguments
        return
    }
    throw "pnpm not found. Install Node.js 20+ with Corepack or install pnpm."
}

function Stop-WebJobs {
    foreach ($job in $jobs) {
        if ($job) {
            Stop-Job $job -ErrorAction SilentlyContinue
            Remove-Job $job -Force -ErrorAction SilentlyContinue
        }
    }
}

function Wait-Http {
    param([string]$Url, [string]$Name, [int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
            Write-Host "$Name is ready." -ForegroundColor Green
            return
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "$Name did not become ready within $TimeoutSeconds seconds: $Url"
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment not found. Create .venv and install services/local-api/requirements.txt."
}

if ($FakeProvider -and $PaidProvider) {
    throw "FakeProvider and PaidProvider are mutually exclusive."
}

trap {
    Stop-WebJobs
    Write-Host "`nZhangwen Web Development Mode stopped." -ForegroundColor Yellow
    break
}

Write-Host "=== Zhangwen Web Development Mode ===" -ForegroundColor Cyan
Write-Host "Interaction baseline: left project creation + one project conversation + @ expert routing." -ForegroundColor Gray
if ($FakeProvider) {
    Write-Host "Provider: explicit local fake (isolated data, no API Key, no model fee)." -ForegroundColor Magenta
}
if ($PaidProvider) {
    Write-Host "Provider: REAL DeepSeek (isolated data; requests will consume paid tokens)." -ForegroundColor Red
    Write-Host "Credential source: backend ZHANGWEN_DEEPSEEK_API_KEY or Windows Credential Manager." -ForegroundColor Red
}
Write-Host "[1/3] Building shared contracts..." -ForegroundColor Yellow
Push-Location (Join-Path $root "packages\contracts")
try {
    Invoke-Pnpm build
    if ($LASTEXITCODE -ne 0) { throw "Contracts build failed." }
}
finally {
    Pop-Location
}

try {
    Write-Host "[2/3] Starting FastAPI: http://127.0.0.1:8100" -ForegroundColor Yellow
    $apiJob = Start-Job -Name "zhangwen-web-api" -ScriptBlock {
        param($root, $fakeProvider, $paidProvider)
        Set-Location $root
        if ($fakeProvider) {
            $env:ZHANGWEN_LLM_TEST_MODE = "fake"
            $env:ZHANGWEN_DEEPSEEK_API_KEY = "local-development-fake-key"
            $env:ZHANGWEN_DATA_DIR = Join-Path $root ".data\web-fake"
        }
        elseif ($paidProvider) {
            $env:ZHANGWEN_LLM_TEST_MODE = "paid"
            $env:ZHANGWEN_DATA_DIR = Join-Path $root ".data\web-paid"
        }
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            & "$root\.venv\Scripts\python.exe" -m uvicorn zhangwen.main:app --port 8100 --host 127.0.0.1 --app-dir services/local-api
        }
        finally {
            $ErrorActionPreference = $previousPreference
        }
    } -ArgumentList $root, $FakeProvider.IsPresent, $PaidProvider.IsPresent
    $jobs += $apiJob

    Write-Host "[3/3] Starting Vite Browser Host: http://localhost:5173" -ForegroundColor Yellow
    $frontendJob = Start-Job -Name "zhangwen-web-vite" -ScriptBlock {
        param($root)
        Set-Location $root
        $env:VITE_ZHANGWEN_HOST = "web"
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $pnpm = Get-Command "pnpm" -ErrorAction SilentlyContinue
        if ($pnpm) {
            try {
                & $pnpm.Source --filter @zhangwen/desktop dev -- --host 127.0.0.1
            }
            finally {
                $ErrorActionPreference = $previousPreference
            }
            return
        }
        $corepack = Get-Command "corepack" -ErrorAction SilentlyContinue
        if ($corepack) {
            try {
                & $corepack.Source pnpm --filter @zhangwen/desktop dev -- --host 127.0.0.1
            }
            finally {
                $ErrorActionPreference = $previousPreference
            }
            return
        }
        throw "pnpm not found."
    } -ArgumentList $root
    $jobs += $frontendJob

    Wait-Http "http://127.0.0.1:8100/api/health" "FastAPI Sidecar"
    Wait-Http "http://127.0.0.1:5173" "Vite Browser Host"
    Write-Host "`nOpen http://localhost:5173" -ForegroundColor Green
    Write-Host "Tauri and Rust are not started. Press Ctrl+C to stop both processes." -ForegroundColor Gray

    while ($true) {
        $failed = $jobs | Where-Object { $_.State -in @("Failed", "Stopped", "Completed") }
        if ($failed) {
            $previousPreference = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            try {
                $failed | Receive-Job -Keep 2>&1 | ForEach-Object { Write-Host $_ }
            }
            finally {
                $ErrorActionPreference = $previousPreference
            }
            throw "A Web Development Mode child process stopped unexpectedly."
        }
        Start-Sleep -Milliseconds 500
    }
}
finally {
    Stop-WebJobs
}

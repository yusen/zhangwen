# Zhangwen local desktop launcher
# Usage: run .\scripts-dev\start-local.ps1 from the repository root.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$viteProcess = $null
$launcherMutex = $null
$hasLauncherMutex = $false
$launcherSessionId = [Guid]::NewGuid().ToString("N")
$logDirectory = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "Zhangwen\logs"
$launcherLogPath = Join-Path $logDirectory "dev-launcher.log"
$viteOwnerPath = Join-Path $logDirectory "dev-vite-owner-v1.json"
$maxLogBytes = 5MB

New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
function Rotate-LocalLog {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path) -or (Get-Item -LiteralPath $Path).Length -le $maxLogBytes) {
        return
    }
    $archivedLogPath = "$Path.1"
    if (Test-Path -LiteralPath $archivedLogPath) {
        Remove-Item -LiteralPath $archivedLogPath -Force
    }
    Move-Item -LiteralPath $Path -Destination $archivedLogPath
}

Rotate-LocalLog -Path $launcherLogPath

function Write-LauncherLog {
    param([string]$Message)

    $timestamp = (Get-Date).ToString("o")
    Add-Content -LiteralPath $launcherLogPath -Encoding utf8 -Value "[$timestamp] [$launcherSessionId] $Message"
}

function Invoke-Pnpm {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    $pnpm = Get-Command "pnpm" -ErrorAction SilentlyContinue
    if ($pnpm) {
        & $pnpm.Source @Arguments
    }
    else {
        $corepack = Get-Command "corepack" -ErrorAction SilentlyContinue
        if (-not $corepack) {
            throw "pnpm not found, and corepack is not available. Install Node.js 20+ with Corepack."
        }
        & $corepack.Source pnpm @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "pnpm $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
    }
}

function Enter-LocalAppMutex {
    $script:launcherMutex = New-Object System.Threading.Mutex($false, "Local\Zhangwen-ZW_V1-CompleteApp")
    try {
        $script:hasLauncherMutex = $script:launcherMutex.WaitOne(0)
    }
    catch [System.Threading.AbandonedMutexException] {
        $script:hasLauncherMutex = $true
    }
    if (-not $script:hasLauncherMutex) {
        $script:launcherMutex.Dispose()
        $script:launcherMutex = $null
        throw "Zhangwen local app is already running from this checkout. Close the existing app before starting it again."
    }
}

function Exit-LocalAppMutex {
    if (-not $script:launcherMutex) {
        return
    }
    try {
        if ($script:hasLauncherMutex) {
            $script:launcherMutex.ReleaseMutex()
        }
    }
    finally {
        $script:launcherMutex.Dispose()
        $script:launcherMutex = $null
        $script:hasLauncherMutex = $false
    }
}

function Stop-LocalJobs {
    if (-not $script:viteProcess) {
        return
    }
    try {
        if (-not $script:viteProcess.HasExited) {
            Stop-Process -Id $script:viteProcess.Id -Force -ErrorAction SilentlyContinue
            $script:viteProcess.WaitForExit(5000) | Out-Null
        }
    }
    finally {
        Remove-ViteOwnerRecord -ProcessId $script:viteProcess.Id
        $script:viteProcess.Dispose()
        $script:viteProcess = $null
    }
}

function Write-ViteOwnerRecord {
    param(
        [Parameter(Mandatory = $true)][System.Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)][string]$NodePath
    )

    $record = [ordered]@{
        schemaVersion = 1
        processId = $Process.Id
        processStartedAt = $Process.StartTime.ToUniversalTime().ToString("o")
        nodePath = [System.IO.Path]::GetFullPath($NodePath)
        workspaceRoot = [System.IO.Path]::GetFullPath($root)
    }
    $temporary = "$viteOwnerPath.$launcherSessionId.tmp"
    $record | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination $viteOwnerPath -Force
}

function Remove-ViteOwnerRecord {
    param([int]$ProcessId)

    if (-not (Test-Path -LiteralPath $viteOwnerPath)) {
        return
    }
    try {
        $record = Get-Content -Raw -Encoding utf8 -LiteralPath $viteOwnerPath | ConvertFrom-Json
        if ([int]$record.processId -eq $ProcessId) {
            Remove-Item -LiteralPath $viteOwnerPath -Force
        }
    }
    catch {
        Write-LauncherLog "Vite owner record could not be read during cleanup."
    }
}

function Stop-StaleOwnedVite {
    if (-not (Test-Path -LiteralPath $viteOwnerPath)) {
        return
    }
    try {
        $record = Get-Content -Raw -Encoding utf8 -LiteralPath $viteOwnerPath | ConvertFrom-Json
        if ([int]$record.schemaVersion -ne 1 -or
            -not ([System.IO.Path]::GetFullPath([string]$record.workspaceRoot)).Equals(
                [System.IO.Path]::GetFullPath($root),
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
            throw "owner record does not belong to this checkout"
        }
        $processId = [int]$record.processId
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if (-not $process) {
            Remove-Item -LiteralPath $viteOwnerPath -Force
            return
        }
        $recordedStart = [DateTime]::Parse([string]$record.processStartedAt).ToUniversalTime()
        $actualStart = $process.StartTime.ToUniversalTime()
        $recordedNode = [System.IO.Path]::GetFullPath([string]$record.nodePath)
        $actualNode = [System.IO.Path]::GetFullPath($process.Path)
        $portOwner = Get-ListeningProcessId -Port 5173
        if ($portOwner -ne $processId -or
            [Math]::Abs(($recordedStart - $actualStart).TotalSeconds) -gt 1 -or
            -not $recordedNode.Equals($actualNode, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "owner record no longer identifies the process listening on port 5173"
        }

        Write-Host "Recovering the previous Zhangwen development session..." -ForegroundColor Yellow
        Write-LauncherLog "Stopping owned stale Vite PID=$processId."
        Stop-Process -Id $processId -Force -ErrorAction Stop
        $deadline = (Get-Date).AddSeconds(5)
        while ((Test-TcpPortOpen -Port 5173) -and (Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 200
        }
        if (Test-TcpPortOpen -Port 5173) {
            throw "owned Vite process did not release port 5173"
        }
        Remove-Item -LiteralPath $viteOwnerPath -Force
    }
    catch {
        throw "A previous Vite owner record exists but could not be verified safely: $($_.Exception.Message). Close the old Zhangwen development process and retry."
    }
}

function Test-TcpPortOpen {
    param([int]$Port)

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $pending = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        return $pending.AsyncWaitHandle.WaitOne(400) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-TcpPort {
    param(
        [int]$Port,
        [string]$Name,
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPortOpen -Port $Port) {
            return
        }
        if ($Process.HasExited) {
            throw "$Name stopped before becoming ready with exit code $($Process.ExitCode)."
        }
        Start-Sleep -Milliseconds 250
    }
    throw "$Name did not listen on 127.0.0.1:$Port within $TimeoutSeconds seconds."
}

function Get-ListeningProcessId {
    param([int]$Port)

    $pattern = "^\s*TCP\s+127\.0\.0\.1:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$"
    foreach ($line in (& "$env:SystemRoot\System32\netstat.exe" -ano -p TCP)) {
        if ($line -match $pattern) {
            return [int]$Matches[1]
        }
    }
    return $null
}

function Report-ExistingSidecar {
    if (-not (Test-TcpPortOpen -Port 8100)) {
        return
    }

    $ownerId = Get-ListeningProcessId -Port 8100
    Write-Warning "Port 8100 is already in use$(if ($ownerId) { " by PID $ownerId" }). The desktop will open in diagnostic mode and will not terminate that process automatically."
    Write-LauncherLog "Sidecar port already occupied$(if ($ownerId) { " PID=$ownerId" }); automatic process termination skipped."
}

function Test-ContractsBuildRequired {
    $contractRoot = Join-Path $root "packages\contracts"
    $outputs = @(
        (Join-Path $contractRoot "dist\index.js"),
        (Join-Path $contractRoot "dist\index.d.ts")
    )
    if ($outputs.Where({ -not (Test-Path -LiteralPath $_) }).Count -gt 0) {
        return $true
    }

    $inputs = @(
        Get-ChildItem -LiteralPath (Join-Path $contractRoot "src") -File -Recurse
        Get-Item -LiteralPath (Join-Path $contractRoot "package.json")
        Get-Item -LiteralPath (Join-Path $contractRoot "tsconfig.json")
    )
    $newestInput = ($inputs | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1).LastWriteTimeUtc
    $oldestOutput = ($outputs | ForEach-Object { Get-Item -LiteralPath $_ } |
        Sort-Object LastWriteTimeUtc | Select-Object -First 1).LastWriteTimeUtc
    return $newestInput -gt $oldestOutput
}

function Test-DesktopBuildRequired {
    $tauriRoot = Join-Path $root "apps\desktop\src-tauri"
    $desktopExecutable = Join-Path $tauriRoot "target\debug\zhangwen-desktop.exe"
    if (-not (Test-Path -LiteralPath $desktopExecutable)) {
        return $true
    }

    $inputs = @(
        Get-ChildItem -LiteralPath (Join-Path $tauriRoot "src") -File -Recurse
        Get-Item -LiteralPath (Join-Path $tauriRoot "Cargo.toml")
        Get-Item -LiteralPath (Join-Path $tauriRoot "Cargo.lock")
        Get-Item -LiteralPath (Join-Path $tauriRoot "tauri.conf.json")
    )
    $newestInput = ($inputs | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1).LastWriteTimeUtc
    $builtAt = (Get-Item -LiteralPath $desktopExecutable).LastWriteTimeUtc
    return $newestInput -gt $builtAt
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment not found. Create .venv and install services/local-api/requirements.txt."
}

Enter-LocalAppMutex
try {
    $totalTimer = [System.Diagnostics.Stopwatch]::StartNew()
    Write-LauncherLog "Launcher session started."
    Write-Host "=== Starting Zhangwen local app ===" -ForegroundColor Cyan

    $phaseTimer = [System.Diagnostics.Stopwatch]::StartNew()
    if (Test-ContractsBuildRequired) {
        Write-Host "[1/2] Shared contracts changed; rebuilding..." -ForegroundColor Yellow
        Push-Location (Join-Path $root "packages\contracts")
        try { Invoke-Pnpm build } finally { Pop-Location }
        Write-LauncherLog "Contracts rebuilt in $($phaseTimer.ElapsedMilliseconds) ms."
    }
    else {
        Write-Host "[1/2] Shared contracts are current; skipping build." -ForegroundColor Green
        Write-LauncherLog "Contracts build skipped after $($phaseTimer.ElapsedMilliseconds) ms."
    }

    Report-ExistingSidecar
    Stop-StaleOwnedVite
    if (Test-TcpPortOpen -Port 5173) {
        $viteOwnerId = Get-ListeningProcessId -Port 5173
        throw "Port 5173 is already in use$(if ($viteOwnerId) { " by PID $viteOwnerId" }). Close the stale Vite process and retry."
    }

    $tokenBytes = New-Object byte[] 32
    $tokenGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $tokenGenerator.GetBytes($tokenBytes)
    }
    finally {
        $tokenGenerator.Dispose()
    }
    $env:ZHANGWEN_DESKTOP_CAPABILITY_TOKEN = [Convert]::ToBase64String($tokenBytes)
    $env:ZHANGWEN_DATA_DIR = Join-Path $root "services\local-api\.data"

    Write-Host "[2/2] Starting Vite and the desktop host (Tauri owns the local Sidecar)..." -ForegroundColor Yellow
    $node = Get-Command "node" -ErrorAction Stop
    $desktopRoot = Join-Path $root "apps\desktop"
    $viteEntrypoint = Join-Path $desktopRoot "node_modules\vite\bin\vite.js"
    if (-not (Test-Path -LiteralPath $viteEntrypoint)) {
        throw "Vite entrypoint not found. Run pnpm install --frozen-lockfile."
    }
    Rotate-LocalLog -Path (Join-Path $logDirectory "vite-dev.stdout.log")
    Rotate-LocalLog -Path (Join-Path $logDirectory "vite-dev.stderr.log")
    $script:viteProcess = Start-Process -FilePath $node.Source `
        -ArgumentList @($viteEntrypoint) `
        -WorkingDirectory $desktopRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDirectory "vite-dev.stdout.log") `
        -RedirectStandardError (Join-Path $logDirectory "vite-dev.stderr.log") `
        -PassThru
    Write-ViteOwnerRecord -Process $script:viteProcess -NodePath $node.Source
    Wait-TcpPort -Port 5173 -Name "Vite" -Process $script:viteProcess

    $tauriRoot = Join-Path $root "apps\desktop\src-tauri"
    $desktopExecutable = Join-Path $tauriRoot "target\debug\zhangwen-desktop.exe"
    if (Test-DesktopBuildRequired) {
        Write-LauncherLog "Rust/Tauri inputs changed; starting cargo run; elapsed=$($totalTimer.ElapsedMilliseconds) ms."
        Push-Location $tauriRoot
        try {
            cargo run
            if ($LASTEXITCODE -ne 0) {
                throw "cargo run failed with exit code $LASTEXITCODE."
            }
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-LauncherLog "Desktop binary is current; launching directly; elapsed=$($totalTimer.ElapsedMilliseconds) ms."
        & $desktopExecutable
        if ($LASTEXITCODE -ne 0) {
            throw "Desktop executable failed with exit code $LASTEXITCODE."
        }
    }
    Write-LauncherLog "Desktop exited normally; total=$($totalTimer.ElapsedMilliseconds) ms."
}
catch {
    Write-LauncherLog "Launcher failed: $($_.Exception.Message)"
    throw
}
finally {
    Stop-LocalJobs
    Exit-LocalAppMutex
    Write-LauncherLog "Launcher cleanup completed."
    Write-Host "Zhangwen local desktop app stopped." -ForegroundColor Yellow
}

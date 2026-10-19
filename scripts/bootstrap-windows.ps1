param([switch]$PrepareOnly, [Parameter(ValueFromRemainingArguments=$true)][string[]]$ServerArgs)
$ErrorActionPreference = 'Stop'
# Use this host's bundled modules before any command can trigger auto-loading.
# A PowerShell 7/automation parent may have supplied incompatible module paths.
$env:PSModulePath = [IO.Path]::Combine($PSHOME, 'Modules')
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot '.runtime'
if ($env:ZHANGWEN_RUNTIME_DIR) { $runtimeRoot = [IO.Path]::GetFullPath($env:ZHANGWEN_RUNTIME_DIR) }
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
Set-Location -LiteralPath $projectRoot
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
. (Join-Path $PSScriptRoot 'runtime-windows.ps1')

function Get-VerifiedArchive([string]$Url, [string]$Name, [string]$Sha256) {
    $archivePath = Join-Path $runtimeRoot $Name
    if ((Test-Path -LiteralPath $archivePath) -and ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash -eq $Sha256)) { return $archivePath }
    Write-Host "Downloading $Name ..."
    $partialPath = "$archivePath.download"
    Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $partialPath -TimeoutSec 600
    if ((Get-FileHash -LiteralPath $partialPath -Algorithm SHA256).Hash -ne $Sha256) { throw "SHA-256 mismatch: $Name. Please retry." }
    Move-Item -LiteralPath $partialPath -Destination $archivePath -Force
    return $archivePath
}

try {
    # A process lock avoids two first-run installers modifying the same runtime.
    try { $setupLock = [IO.File]::Open((Join-Path $runtimeRoot 'bootstrap.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw 'Another installer is running for this folder. Please use its window.' }
    try {
        Write-Host 'Checking installed Node.js, npm and Python (offline) ...'
        $nodeDir = Join-Path $runtimeRoot 'node-v24.14.0-win-x64'
        $nodeExe = Join-Path $nodeDir 'node.exe'
        $nodeRuntime = $null
        foreach ($candidate in (@($nodeExe) + @(Get-ApplicationPaths @('node.exe', 'node')) | Select-Object -Unique)) {
            $nodeRuntime = Get-NodeRuntime $candidate
            if ($nodeRuntime) { break }
        }
        if (!$nodeRuntime) {
            Write-Host 'No working Node.js 22+ with npm was found. Preparing project-local Node.js ...'
            $nodeUrl = 'https://cdn.npmmirror.com/binaries/node/v24.14.0/node-v24.14.0-win-x64.zip'
            $nodeZip = Get-VerifiedArchive $nodeUrl 'node-v24.14.0-win-x64.zip' '313fa40c0d7b18575821de8cb17483031fe07d95de5994f6f435f3b345f85c66'
            Expand-Archive -LiteralPath $nodeZip -DestinationPath $runtimeRoot -Force
            $nodeRuntime = Get-NodeRuntime $nodeExe
            if (!$nodeRuntime) { throw 'The downloaded Node.js/npm runtime did not pass its execution check.' }
        }
        $nodeExe = $nodeRuntime.Executable
        $env:PATH = "$(Split-Path -Parent $nodeExe);$env:PATH"
        $env:ZHANGWEN_NPM_CLI = $nodeRuntime.NpmCli
        Write-Host "Using Node.js $($nodeRuntime.Version), npm $($nodeRuntime.NpmVersion): $nodeExe"
        $pythonExe = Join-Path $projectRoot '.venv/Scripts/python.exe'
        $pythonRuntime = Get-PythonRuntime $pythonExe
        if ($pythonRuntime -and !$pythonRuntime.IsVenv) { $pythonRuntime = $null }
        if (!$pythonRuntime) {
            $basePython = $null
            $pythonCandidates = @($env:ZHANGWEN_PYTHON) + @(Get-ApplicationPaths @('python.exe', 'python3.exe', 'python', 'python3'))
            $managedPythonRoot = Join-Path $runtimeRoot 'python'
            if (Test-Path -LiteralPath $managedPythonRoot) {
                $pythonCandidates += @(Get-ChildItem -LiteralPath $managedPythonRoot -Filter python.exe -Recurse -File | ForEach-Object { $_.FullName })
            }
            foreach ($candidate in ($pythonCandidates | Select-Object -Unique)) {
                $basePython = Get-PythonRuntime $candidate -RequireVenvSupport
                if ($basePython) { break }
            }
            if (!$basePython) {
                foreach ($launcher in @(Get-ApplicationPaths @('py.exe', 'py'))) {
                    foreach ($selector in @('-3', '-3.13', '-3.14', '-3.12')) {
                        $basePython = Get-PythonRuntime $launcher $selector -RequireVenvSupport
                        if ($basePython) { break }
                    }
                    if ($basePython) { break }
                }
            }
            if (!$basePython) {
                Write-Host 'No working Python with venv support was found. Preparing standalone Python ...'
                # Pinned standalone build and digest, fetched from the domestic mirror.
                $pythonName = 'cpython-3.13.7+20250918-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
                $pythonUrlName = [uri]::EscapeDataString($pythonName)
                $pythonUrl = "https://cdn.npmmirror.com/binaries/python-build-standalone/20250918/$pythonUrlName"
                $pythonArchive = Get-VerifiedArchive $pythonUrl $pythonName 'bc229e5364699a8456b6ceabde8348c75e62312ffd62631dd1e494a1755a45ed'
                $pythonHome = Join-Path $managedPythonRoot 'cpython-3.13.7-20250918'
                if (Test-Path -LiteralPath $pythonHome) { throw "Unusable managed Python preserved: $pythonHome. Rename it and retry." }
                $stage = Join-Path $runtimeRoot ('python-extract-' + [guid]::NewGuid().ToString('N'))
                New-Item -ItemType Directory -Path $stage | Out-Null
                & (Join-Path $env:SystemRoot 'System32/tar.exe') -xzf $pythonArchive -C $stage
                if ($LASTEXITCODE -ne 0) { throw 'Could not extract the verified Python archive.' }
                $stagedPython = Get-PythonRuntime (Join-Path $stage 'python/python.exe') -RequireVenvSupport
                if (!$stagedPython) { throw 'The downloaded Python runtime did not pass its venv/ensurepip check.' }
                New-Item -ItemType Directory -Force -Path $managedPythonRoot | Out-Null
                Move-Item -LiteralPath (Join-Path $stage 'python') -Destination $pythonHome
                Remove-Item -LiteralPath $stage
                $basePython = Get-PythonRuntime (Join-Path $pythonHome 'python.exe') -RequireVenvSupport
                if (!$basePython) { throw 'The standalone Python runtime did not pass its execution check.' }
            }
            $venvDir = Join-Path $projectRoot '.venv'
            if (Test-Path -LiteralPath $venvDir) {
                $venvItem = Get-Item -LiteralPath $venvDir -Force
                if ($venvItem.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'The invalid .venv is a link. Please fix or unlink it before retrying.' }
                $localRecovery = Join-Path $projectRoot '.runtime'
                New-Item -ItemType Directory -Force -Path $localRecovery | Out-Null
                $backupVenv = Join-Path $localRecovery ('venv-invalid-' + [guid]::NewGuid().ToString('N'))
                $workspacePrefix = [IO.Path]::GetFullPath($projectRoot).TrimEnd('\') + '\'
                foreach ($checkedPath in @($venvDir, $backupVenv)) {
                    if (![IO.Path]::GetFullPath($checkedPath).StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing to move an environment outside the project.' }
                }
                Move-Item -LiteralPath $venvDir -Destination $backupVenv
                Write-Host "Preserved unusable .venv at $backupVenv"
            }
            Write-Host "Using Python $($basePython.Version): $($basePython.Executable)"
            Write-Host 'Creating isolated project dependencies in .venv ...'
            & $basePython.Executable -m venv $venvDir
            if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv using the detected Python. Check its venv support and retry.' }
            $pythonRuntime = Get-PythonRuntime $pythonExe
            if (!$pythonRuntime -or !$pythonRuntime.IsVenv) { throw 'The project Python environment did not pass its execution check.' }
        }
        Write-Host "Using project Python $($pythonRuntime.Version): $($pythonRuntime.Executable)"
    } finally { $setupLock.Dispose() }
    $setupArgs = @('scripts/setup.mjs')
    if ($PrepareOnly) { $setupArgs += '--prepare-only' }
    if ($ServerArgs) { $setupArgs += $ServerArgs }
    & $nodeExe @setupArgs
    exit $LASTEXITCODE
} catch {
    Write-Host "`nStartup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'No system PATH or credentials were changed. Fix the error and double-click start-web.bat again.'
    exit 1
}

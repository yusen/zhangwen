param([switch]$PrepareOnly, [Parameter(ValueFromRemainingArguments=$true)][string[]]$ServerArgs)
$ErrorActionPreference = 'Stop'
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
    Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $partialPath
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
            $nodeZip = Get-VerifiedArchive 'https://nodejs.org/dist/v24.14.0/node-v24.14.0-win-x64.zip' 'node-v24.14.0-win-x64.zip' '313fa40c0d7b18575821de8cb17483031fe07d95de5994f6f435f3b345f85c66'
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
                $basePython = Get-PythonRuntime $candidate
                if ($basePython) { break }
            }
            if (!$basePython) {
                foreach ($launcher in @(Get-ApplicationPaths @('py.exe', 'py'))) {
                    foreach ($selector in @('-3', '-3.13', '-3.14', '-3.12', '-3.11')) {
                        $basePython = Get-PythonRuntime $launcher $selector
                        if ($basePython) { break }
                    }
                    if ($basePython) { break }
                }
            }
            $uvDir = Join-Path $runtimeRoot 'uv'
            $uvExe = Get-UvRuntime (@((Join-Path $uvDir 'uv.exe')) + @(Get-ApplicationPaths @('uv.exe', 'uv')))
            if (!$basePython -and $uvExe) {
                $uvPython = Invoke-RuntimeProbe $uvExe 'python find --offline ">=3.11"'
                if ($uvPython) { $basePython = Get-PythonRuntime $uvPython }
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
            if ($basePython) {
                Write-Host "Using installed Python $($basePython.Version): $($basePython.Executable)"
                Write-Host 'Creating isolated project dependencies in .venv ...'
                & $basePython.Executable -m venv $venvDir
                if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv using the detected Python. Check its venv support and retry.' }
            } else {
              if (!$uvExe) {
                Write-Host 'No working Python 3.11+ was found. Preparing project-local uv/Python ...'
                $uvZip = Get-VerifiedArchive 'https://github.com/astral-sh/uv/releases/download/0.8.22/uv-x86_64-pc-windows-msvc.zip' 'uv-0.8.22-win-x64.zip' '5049375aa2a5162f132b2c1cb992e25d42d47d934cab8c174dbe6f60973dcc12'
                Expand-Archive -LiteralPath $uvZip -DestinationPath $uvDir -Force
                $uvExe = Get-UvRuntime @((Join-Path $uvDir 'uv.exe'))
                if (!$uvExe) { throw 'The downloaded uv runtime did not pass its execution check.' }
              }
              $env:UV_PYTHON_INSTALL_DIR = $managedPythonRoot
              $env:UV_CACHE_DIR = Join-Path $projectRoot '.cache/uv'
              $env:UV_NO_MODIFY_PATH = '1'
              $env:UV_NATIVE_TLS = 'true'
              & $uvExe venv --python 3.13.7 --managed-python --seed $venvDir
              if ($LASTEXITCODE -ne 0) { throw 'Python setup failed. Check your connection to GitHub and PyPI, then run again.' }
            }
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

param([switch]$PrepareOnly, [Parameter(ValueFromRemainingArguments=$true)][string[]]$ServerArgs)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
Set-Location -LiteralPath $projectRoot
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

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
        # Windows x64 runtime also works under Windows 11 ARM64 x64 emulation.
        $nodeDir = Join-Path $runtimeRoot 'node-v24.14.0-win-x64'
        $nodeExe = Join-Path $nodeDir 'node.exe'
        if (!(Test-Path -LiteralPath $nodeExe)) {
            $nodeZip = Get-VerifiedArchive 'https://nodejs.org/dist/v24.14.0/node-v24.14.0-win-x64.zip' 'node-v24.14.0-win-x64.zip' '313fa40c0d7b18575821de8cb17483031fe07d95de5994f6f435f3b345f85c66'
            Expand-Archive -LiteralPath $nodeZip -DestinationPath $runtimeRoot -Force
        }
        $env:PATH = "$nodeDir;$env:PATH"
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $runtimeRoot 'python'
        $env:UV_CACHE_DIR = Join-Path $projectRoot '.cache/uv'
        $env:UV_NO_MODIFY_PATH = '1'
        $env:UV_NATIVE_TLS = 'true'
        $pythonExe = Join-Path $projectRoot '.venv/Scripts/python.exe'
        if (!(Test-Path -LiteralPath $pythonExe)) {
            $uvDir = Join-Path $runtimeRoot 'uv'
            $uvExe = Join-Path $uvDir 'uv.exe'
            if (!(Test-Path -LiteralPath $uvExe)) {
                $uvZip = Get-VerifiedArchive 'https://github.com/astral-sh/uv/releases/download/0.8.22/uv-x86_64-pc-windows-msvc.zip' 'uv-0.8.22-win-x64.zip' '5049375aa2a5162f132b2c1cb992e25d42d47d934cab8c174dbe6f60973dcc12'
                Expand-Archive -LiteralPath $uvZip -DestinationPath $uvDir -Force
            }
            Write-Host 'Preparing project-local Python 3.13.7 ...'
            & $uvExe venv --python 3.13.7 --managed-python --seed (Join-Path $projectRoot '.venv')
            if ($LASTEXITCODE -ne 0) { throw 'Python setup failed. Check your connection to GitHub and PyPI, then run again.' }
        }
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

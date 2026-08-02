[CmdletBinding()]
param(
    [switch]$Check
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tauriRoot = Join-Path $root "apps\desktop\src-tauri"
$configPath = Join-Path $tauriRoot "tauri.conf.json"
$versioningScript = Join-Path $PSScriptRoot "installer-versioning.ps1"
$buildScript = Join-Path $PSScriptRoot "build-windows-package.ps1"
$verifyScript = Join-Path $PSScriptRoot "verify-windows-package.ps1"
$requiredBrandAssets = @(
    (Join-Path $root "assets\branding\logo.png"),
    (Join-Path $tauriRoot "icons\icon.ico"),
    (Join-Path $root "apps\desktop\public\app-logo.png")
)

. $versioningScript

foreach ($path in @($versioningScript, $buildScript, $verifyScript, $configPath) + $requiredBrandAssets) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required installer input is missing: $path"
    }
}

$currentVersion = Get-ZhangwenTauriVersion -ConfigPath $configPath
$nextVersion = Get-ZhangwenNextInstallerVersion -Version $currentVersion
if ($Check) {
    Write-Host "Installer workflow OK: current $currentVersion, next successful build $nextVersion" -ForegroundColor Green
    exit 0
}

$lockDirectory = Join-Path $tauriRoot "target\packaging"
New-Item -ItemType Directory -Force -Path $lockDirectory | Out-Null
$lockPath = Join-Path $lockDirectory "version-build.lock"
$lockStream = $null
try {
    try {
        $lockStream = [System.IO.File]::Open(
            $lockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    }
    catch [System.IO.IOException] {
        throw "Another installer build is already running. Wait for it to finish before starting a new build."
    }

    Invoke-ZhangwenInstallerVersionTransaction -ConfigPath $configPath -Action {
        param([string]$Version)

        Write-Host "Building Zhangwen installer version $Version..." -ForegroundColor Cyan
        & powershell -NoProfile -ExecutionPolicy Bypass -File $buildScript
        if ($LASTEXITCODE -ne 0) {
            throw "Installer build failed with exit code $LASTEXITCODE."
        }

        Write-Host "Verifying Zhangwen installer version $Version..." -ForegroundColor Cyan
        & powershell -NoProfile -ExecutionPolicy Bypass -File $verifyScript
        if ($LASTEXITCODE -ne 0) {
            throw "Installer verification failed with exit code $LASTEXITCODE."
        }
    } | Out-Host
}
catch {
    Write-Warning "The installer was not accepted; the version remains $currentVersion."
    throw
}
finally {
    if ($lockStream) {
        $lockStream.Dispose()
    }
}

$completedVersion = Get-ZhangwenTauriVersion -ConfigPath $configPath
$bundleDirectory = Join-Path $tauriRoot "target\release\bundle\nsis"
$installer = Get-ChildItem -LiteralPath $bundleDirectory -Filter "*.exe" -File |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
Write-Host "Installer $completedVersion built and verified successfully." -ForegroundColor Green
if ($installer) {
    Write-Host "Output: $($installer.FullName)"
}

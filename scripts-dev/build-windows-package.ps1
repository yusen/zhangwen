[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$desktopRoot = Join-Path $root "apps\desktop"
$tauriRoot = Join-Path $desktopRoot "src-tauri"
$tauriConfigPath = Join-Path $tauriRoot "tauri.conf.json"

if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
    throw "The Zhangwen NSIS installer can only be built on Windows."
}

Push-Location $root
try {
    & pnpm --filter @zhangwen/contracts build
    if ($LASTEXITCODE -ne 0) {
        throw "Contracts build failed with exit code $LASTEXITCODE."
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File scripts-dev\build-windows-sidecar.ps1
    if ($LASTEXITCODE -ne 0) {
        throw "Sidecar packaging failed with exit code $LASTEXITCODE."
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File scripts-dev\test-packaged-sidecar.ps1
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged Sidecar smoke test failed with exit code $LASTEXITCODE."
    }

    $previousEncodedRustFlags = $env:CARGO_ENCODED_RUSTFLAGS
    $remapFlags = @("--remap-path-prefix=$root=zhangwen-source")
    if ($env:USERPROFILE) {
        $remapFlags += "--remap-path-prefix=$env:USERPROFILE=build-user"
    }
    $encodedRemapFlags = $remapFlags -join [char]0x1f
    if ($previousEncodedRustFlags) {
        $env:CARGO_ENCODED_RUSTFLAGS = "$previousEncodedRustFlags$([char]0x1f)$encodedRemapFlags"
    }
    else {
        $env:CARGO_ENCODED_RUSTFLAGS = $encodedRemapFlags
    }

    Push-Location $desktopRoot
    try {
        & pnpm exec tauri build --bundles nsis
        if ($LASTEXITCODE -ne 0) {
            throw "Tauri NSIS build failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
        if ($null -eq $previousEncodedRustFlags) {
            Remove-Item Env:CARGO_ENCODED_RUSTFLAGS -ErrorAction SilentlyContinue
        }
        else {
            $env:CARGO_ENCODED_RUSTFLAGS = $previousEncodedRustFlags
        }
    }
}
finally {
    Pop-Location
}

$bundleDir = Join-Path $tauriRoot "target\release\bundle\nsis"
$installer = Get-ChildItem -LiteralPath $bundleDir -Filter "*.exe" -File -ErrorAction Stop |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if (-not $installer) {
    throw "Tauri completed without producing an NSIS installer in $bundleDir."
}

$sidecarExe = Join-Path $tauriRoot "resources\sidecar\zhangwen-sidecar\zhangwen-sidecar.exe"
$tauriConfig = Get-Content -Raw -Encoding utf8 -LiteralPath $tauriConfigPath | ConvertFrom-Json
$manifest = [ordered]@{
    product = $tauriConfig.productName
    version = $tauriConfig.version
    architecture = "x86_64-pc-windows-msvc"
    installer = $installer.Name
    installerSizeBytes = $installer.Length
    installerSha256 = (Get-FileHash -LiteralPath $installer.FullName -Algorithm SHA256).Hash
    sidecarSha256 = (Get-FileHash -LiteralPath $sidecarExe -Algorithm SHA256).Hash
    webview2InstallMode = "offlineInstaller"
    signed = (Get-AuthenticodeSignature -LiteralPath $installer.FullName).Status -eq "Valid"
    generatedAt = (Get-Date).ToUniversalTime().ToString("o")
}
$manifestPath = Join-Path $bundleDir "package-manifest.json"
$manifest | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding utf8

Write-Host "Windows installer ready: $($installer.FullName)" -ForegroundColor Green
Write-Host "Installer SHA256: $($manifest.installerSha256)"
Write-Host "Build manifest: $manifestPath"

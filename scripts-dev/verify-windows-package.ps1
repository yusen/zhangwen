[CmdletBinding()]
param(
    [switch]$InstallSmoke,
    [switch]$DesktopSmoke
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tauriRoot = Join-Path $root "apps\desktop\src-tauri"
$bundleDir = Join-Path $tauriRoot "target\release\bundle\nsis"
$installer = Get-ChildItem -LiteralPath $bundleDir -Filter "*.exe" -File -ErrorAction Stop |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if (-not $installer) {
    throw "No NSIS installer found in $bundleDir."
}

$config = Get-Content -Raw -Encoding utf8 (Join-Path $tauriRoot "tauri.conf.json") | ConvertFrom-Json
if ($config.bundle.windows.webviewInstallMode.type -ne "offlineInstaller") {
    throw "Tauri WebView2 install mode is not offlineInstaller."
}
if ($config.bundle.windows.allowDowngrades -ne $false) {
    throw "Tauri installer still permits unsafe application downgrades."
}

$manifestPath = Join-Path $bundleDir "package-manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Build manifest not found at $manifestPath. Run pnpm package:windows first."
}
$manifest = Get-Content -Raw -Encoding utf8 -LiteralPath $manifestPath | ConvertFrom-Json
$installerHash = (Get-FileHash -LiteralPath $installer.FullName -Algorithm SHA256).Hash
if ($manifest.product -ne $config.productName -or $manifest.version -ne $config.version) {
    throw "Build manifest product/version does not match tauri.conf.json."
}
if ($manifest.installer -ne $installer.Name -or
    [int64]$manifest.installerSizeBytes -ne [int64]$installer.Length -or
    $manifest.installerSha256 -ne $installerHash) {
    throw "Build manifest does not match the current installer."
}
if ($manifest.webview2InstallMode -ne "offlineInstaller") {
    throw "Build manifest does not record offline WebView2 installation."
}

$releaseExe = Join-Path $tauriRoot "target\release\zhangwen-desktop.exe"
$sidecarDir = Join-Path $tauriRoot "resources\sidecar\zhangwen-sidecar"
$sidecarExe = Join-Path $sidecarDir "zhangwen-sidecar.exe"
foreach ($binary in @($releaseExe, $sidecarExe)) {
    if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) {
        throw "Expected packaged binary is missing: $binary"
    }
}
$sidecarHash = (Get-FileHash -LiteralPath $sidecarExe -Algorithm SHA256).Hash
if ($manifest.sidecarSha256 -ne $sidecarHash) {
    throw "Build manifest does not match the current Sidecar executable."
}

function Test-BinaryContainsText {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Text
    )
    $ascii = [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($Path))
    return $ascii.IndexOf($Text, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Restore-EnvironmentValue {
    param([string]$Name, [AllowNull()][string]$Value)
    if ($null -eq $Value) {
        Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
    }
    else {
        Set-Item -LiteralPath "Env:$Name" -Value $Value
    }
}

function Test-InstalledPackage {
    param(
        [Parameter(Mandatory = $true)][System.IO.FileInfo]$Installer,
        [Parameter(Mandatory = $true)][string]$ProductName
    )

    $existingInstall = Get-ChildItem "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall" -ErrorAction SilentlyContinue |
        ForEach-Object { Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue } |
        Where-Object { $_.DisplayName -eq $ProductName } |
        Select-Object -First 1
    if ($existingInstall) {
        throw "Install smoke refused because '$ProductName' is already installed for this user. Uninstall it or use an isolated Windows VM."
    }

    $smokeRoot = Join-Path $env:TEMP ("zhangwen-installer-smoke-" + [Guid]::NewGuid().ToString("N"))
    $installRoot = Join-Path $smokeRoot "install"
    $dataDir = Join-Path $smokeRoot "data"
    $process = $null
    $saved = @{
        PATH = $env:PATH
        ZHANGWEN_DATA_DIR = $env:ZHANGWEN_DATA_DIR
        ZHANGWEN_DESKTOP_CAPABILITY_TOKEN = $env:ZHANGWEN_DESKTOP_CAPABILITY_TOKEN
        ZHANGWEN_SIDECAR_PORT = $env:ZHANGWEN_SIDECAR_PORT
    }

    try {
        New-Item -ItemType Directory -Force -Path $smokeRoot | Out-Null
        $installProcess = Start-Process -FilePath $Installer.FullName -ArgumentList @("/S", "/D=$installRoot") -PassThru -Wait
        if ($installProcess.ExitCode -ne 0) {
            throw "Installer exited with code $($installProcess.ExitCode)."
        }

        $desktopExe = Join-Path $installRoot "zhangwen-desktop.exe"
        $installedSidecar = Join-Path $installRoot "sidecar\zhangwen-sidecar\zhangwen-sidecar.exe"
        if (-not (Test-Path -LiteralPath $desktopExe -PathType Leaf) -or
            -not (Test-Path -LiteralPath $installedSidecar -PathType Leaf)) {
            throw "Installed desktop executable or Sidecar is missing."
        }

        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
        $listener.Start()
        $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
        $listener.Stop()
        $token = [Guid]::NewGuid().ToString("N")
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
        $env:ZHANGWEN_DATA_DIR = $dataDir
        $env:ZHANGWEN_SIDECAR_PORT = [string]$port
        $env:ZHANGWEN_DESKTOP_CAPABILITY_TOKEN = $token
        $process = Start-Process -FilePath $installedSidecar -ArgumentList "serve" -PassThru -WindowStyle Hidden
        $baseUrl = "http://127.0.0.1:$port"
        $deadline = (Get-Date).AddSeconds(30)
        do {
            if ($process.HasExited) {
                throw "Installed Sidecar exited before health was ready (exit $($process.ExitCode))."
            }
            try {
                $health = Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 2
                break
            }
            catch {
                Start-Sleep -Milliseconds 300
            }
        } while ((Get-Date) -lt $deadline)
        if (-not $health -or $health.status -ne "ok") {
            throw "Installed Sidecar health endpoint did not become ready."
        }

        $headers = @{
            "X-Zhangwen-Host" = "tauri"
            "X-Zhangwen-Capability-Token" = $token
        }
        $capability = Invoke-RestMethod -Uri "$baseUrl/api/health/desktop-capability" -Headers $headers -TimeoutSec 5
        if ($capability.desktopCapability -ne $true) {
            throw "Installed Sidecar capability-token validation failed."
        }
        if (-not (Test-Path -LiteralPath (Join-Path $dataDir "projects\zhangwen.sqlite3") -PathType Leaf) -or
            -not (Test-Path -LiteralPath (Join-Path $dataDir "config") -PathType Container)) {
            throw "Installed Sidecar did not initialize its user data directory."
        }
        Write-Host "Installed package smoke test passed without Node.js or Python on PATH." -ForegroundColor Green
    }
    finally {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $process.WaitForExit(5000) | Out-Null
        }
        foreach ($entry in $saved.GetEnumerator()) {
            Restore-EnvironmentValue -Name $entry.Key -Value $entry.Value
        }
        if (Test-Path -LiteralPath $installRoot) {
            $uninstaller = Join-Path $installRoot "uninstall.exe"
            if (Test-Path -LiteralPath $uninstaller -PathType Leaf) {
                $uninstallProcess = Start-Process -FilePath $uninstaller -ArgumentList "/S" -PassThru -Wait
                if ($uninstallProcess.ExitCode -ne 0) {
                    throw "Installed package uninstaller exited with code $($uninstallProcess.ExitCode)."
                }
            }
        }
        $resolvedTemp = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
        $resolvedSmokeRoot = [System.IO.Path]::GetFullPath($smokeRoot)
        if ($resolvedSmokeRoot.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedSmokeRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Test-InstalledDesktop {
    param(
        [Parameter(Mandatory = $true)][System.IO.FileInfo]$Installer,
        [Parameter(Mandatory = $true)][string]$ProductName
    )

    $existingPort = Get-NetTCPConnection -LocalPort 8100 -State Listen -ErrorAction SilentlyContinue
    if ($existingPort) {
        throw "Desktop smoke refused because port 8100 is occupied. Close the existing local application or use an isolated Windows VM."
    }
    $existingInstall = Get-ChildItem "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall" -ErrorAction SilentlyContinue |
        ForEach-Object { Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue } |
        Where-Object { $_.DisplayName -eq $ProductName } |
        Select-Object -First 1
    if ($existingInstall) {
        throw "Desktop smoke refused because '$ProductName' is already installed for this user. Uninstall it or use an isolated Windows VM."
    }

    $dataDir = Join-Path $env:LOCALAPPDATA "Zhangwen"
    if (Test-Path -LiteralPath $dataDir) {
        throw "Desktop smoke refused because user data already exists at $dataDir. Use an isolated Windows VM."
    }

    $smokeRoot = Join-Path $env:TEMP ("zhangwen-desktop-smoke-" + [Guid]::NewGuid().ToString("N"))
    $installRoot = Join-Path $smokeRoot "install"
    $desktop = $null
    $sidecarProcessId = $null
    $saved = @{
        PATH = $env:PATH
        ZHANGWEN_DATA_DIR = $env:ZHANGWEN_DATA_DIR
        ZHANGWEN_DESKTOP_CAPABILITY_TOKEN = $env:ZHANGWEN_DESKTOP_CAPABILITY_TOKEN
    }

    try {
        New-Item -ItemType Directory -Force -Path $smokeRoot | Out-Null
        $installProcess = Start-Process -FilePath $Installer.FullName -ArgumentList @("/S", "/D=$installRoot") -PassThru -Wait
        if ($installProcess.ExitCode -ne 0) {
            throw "Installer exited with code $($installProcess.ExitCode)."
        }

        $desktopExe = Join-Path $installRoot "zhangwen-desktop.exe"
        $installedSidecar = Join-Path $installRoot "sidecar\zhangwen-sidecar\zhangwen-sidecar.exe"
        if (-not (Test-Path -LiteralPath $desktopExe -PathType Leaf) -or
            -not (Test-Path -LiteralPath $installedSidecar -PathType Leaf)) {
            throw "Installed desktop executable or Sidecar is missing."
        }

        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
        $env:ZHANGWEN_DATA_DIR = Join-Path $smokeRoot "ignored-release-data-dir"
        $env:ZHANGWEN_DESKTOP_CAPABILITY_TOKEN = "ignored-release-token"
        $desktop = Start-Process -FilePath $desktopExe -PassThru -WindowStyle Hidden
        $deadline = (Get-Date).AddSeconds(40)
        do {
            if ($desktop.HasExited) {
                throw "Installed desktop exited before health was ready (exit $($desktop.ExitCode))."
            }
            try {
                $health = Invoke-RestMethod -Uri "http://127.0.0.1:8100/api/health" -TimeoutSec 2
                break
            }
            catch {
                Start-Sleep -Milliseconds 400
            }
        } while ((Get-Date) -lt $deadline)
        if (-not $health -or $health.status -ne "ok") {
            throw "Installed desktop did not start a healthy Sidecar."
        }

        $sidecarListener = Get-NetTCPConnection -LocalPort 8100 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if (-not $sidecarListener) {
            throw "Installed desktop health responded but no Sidecar listener remains on port 8100."
        }
        $sidecarProcessId = [int]$sidecarListener.OwningProcess
        $sidecar = Get-CimInstance Win32_Process -Filter "ProcessId = $sidecarProcessId" -ErrorAction SilentlyContinue
        $expectedSidecarPath = [System.IO.Path]::GetFullPath($installedSidecar)
        $actualSidecarPath = if ($sidecar -and $sidecar.ExecutablePath) {
            [System.IO.Path]::GetFullPath($sidecar.ExecutablePath)
        }
        else {
            $null
        }
        if (-not $actualSidecarPath -or
            -not $actualSidecarPath.Equals($expectedSidecarPath, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Installed desktop did not start its bundled Sidecar."
        }
        if (-not (Test-Path -LiteralPath (Join-Path $dataDir "projects\zhangwen.sqlite3") -PathType Leaf) -or
            -not (Test-Path -LiteralPath (Join-Path $dataDir "config") -PathType Container)) {
            throw "Installed desktop did not initialize SQLite/config in LOCALAPPDATA."
        }
        if (Test-Path -LiteralPath (Join-Path $smokeRoot "ignored-release-data-dir")) {
            throw "Installed desktop accepted an external release data directory override."
        }
        Write-Host "Installed desktop smoke test passed without Node.js or Python on PATH." -ForegroundColor Green
    }
    finally {
        foreach ($entry in $saved.GetEnumerator()) {
            Restore-EnvironmentValue -Name $entry.Key -Value $entry.Value
        }
        if ($desktop -and -not $desktop.HasExited) {
            $null = $desktop.CloseMainWindow()
            if (-not $desktop.WaitForExit(8000)) {
                Stop-Process -Id $desktop.Id -Force -ErrorAction SilentlyContinue
                $desktop.WaitForExit(3000) | Out-Null
            }
        }
        if ($sidecarProcessId) {
            Stop-Process -Id $sidecarProcessId -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $installRoot) {
            $uninstaller = Join-Path $installRoot "uninstall.exe"
            if (Test-Path -LiteralPath $uninstaller -PathType Leaf) {
                $uninstallProcess = Start-Process -FilePath $uninstaller -ArgumentList "/S" -PassThru -Wait
                if ($uninstallProcess.ExitCode -ne 0) {
                    throw "Installed desktop uninstaller exited with code $($uninstallProcess.ExitCode)."
                }
            }
        }
        if (Test-Path -LiteralPath $dataDir) {
            Remove-Item -LiteralPath $dataDir -Recurse -Force
        }
        $resolvedTemp = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
        $resolvedSmokeRoot = [System.IO.Path]::GetFullPath($smokeRoot)
        if ($resolvedSmokeRoot.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedSmokeRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

$forbiddenBuildPaths = @($root)
if ($env:USERPROFILE) {
    $forbiddenBuildPaths += $env:USERPROFILE
}
$packageScanTargets = @($installer.FullName, $releaseExe) + @(
    Get-ChildItem -LiteralPath $sidecarDir -Recurse -File | Select-Object -ExpandProperty FullName
)
foreach ($binary in $packageScanTargets) {
    foreach ($forbiddenPath in $forbiddenBuildPaths) {
        if (Test-BinaryContainsText -Path $binary -Text $forbiddenPath) {
            throw "Packaged binary contains a build-machine absolute path '$forbiddenPath': $binary"
        }
    }
}

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts-dev\test-packaged-sidecar.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Packaged Sidecar verification failed with exit code $LASTEXITCODE."
}

if ($InstallSmoke) {
    Test-InstalledPackage -Installer $installer -ProductName $config.productName
}
if ($DesktopSmoke) {
    Test-InstalledDesktop -Installer $installer -ProductName $config.productName
}

$signature = Get-AuthenticodeSignature -LiteralPath $installer.FullName
$hash = $installerHash
Write-Host "Installer verification passed: $($installer.FullName)" -ForegroundColor Green
Write-Host "Size: $($installer.Length) bytes"
Write-Host "SHA256: $hash"
Write-Host "Authenticode status: $($signature.Status)"
if ($signature.Status -ne "Valid") {
    Write-Warning "The local installer is unsigned and may trigger Windows SmartScreen."
}

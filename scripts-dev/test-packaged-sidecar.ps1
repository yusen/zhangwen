[CmdletBinding()]
param(
    [string]$SidecarDir = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $SidecarDir) {
    $SidecarDir = Join-Path $root "apps\desktop\src-tauri\resources\sidecar\zhangwen-sidecar"
}
$sidecarDirPath = [System.IO.Path]::GetFullPath($SidecarDir)
$sidecarExe = Join-Path $sidecarDirPath "zhangwen-sidecar.exe"
if (-not (Test-Path -LiteralPath $sidecarExe -PathType Leaf)) {
    throw "Packaged Sidecar not found at $sidecarExe."
}
$catalogManifestFile = Get-ChildItem -LiteralPath $sidecarDirPath -Recurse `
    -Filter "hardware-catalog-manifest.json" -File | Select-Object -First 1
if (-not $catalogManifestFile) {
    throw "Packaged hardware catalog manifest is missing from $sidecarDirPath."
}
$catalogManifest = Get-Content -Raw -Encoding utf8 -LiteralPath $catalogManifestFile.FullName |
    ConvertFrom-Json
if ($catalogManifest.schema -ne "zhangwen.packaged-hardware-catalog/v1" -or
    $catalogManifest.activeCount -lt 1) {
    throw "Packaged hardware catalog manifest is invalid or empty."
}

$smokeRoot = Join-Path $root "apps\desktop\src-tauri\target\package-smoke"
$runRoot = Join-Path $smokeRoot ([Guid]::NewGuid().ToString("N"))
$dataDir = Join-Path $runRoot "data"
$workspace = Join-Path $runRoot "validation"
New-Item -ItemType Directory -Force -Path (Join-Path $workspace "src"), $dataDir | Out-Null
[System.IO.File]::WriteAllText(
    (Join-Path $workspace "src\main.py"),
    "print('packaged validation')`n",
    [System.Text.UTF8Encoding]::new($false)
)

$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
$listener.Stop()
$token = [Guid]::NewGuid().ToString("N")
$process = $null

$saved = @{
    PATH = $env:PATH
    ZHANGWEN_DATA_DIR = $env:ZHANGWEN_DATA_DIR
    ZHANGWEN_DESKTOP_CAPABILITY_TOKEN = $env:ZHANGWEN_DESKTOP_CAPABILITY_TOKEN
    ZHANGWEN_SIDECAR_PORT = $env:ZHANGWEN_SIDECAR_PORT
    ZHANGWEN_DEEPSEEK_API_KEY = $env:ZHANGWEN_DEEPSEEK_API_KEY
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

try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:ZHANGWEN_DATA_DIR = $dataDir
    $env:ZHANGWEN_DESKTOP_CAPABILITY_TOKEN = $token
    $env:ZHANGWEN_SIDECAR_PORT = [string]$port
    Remove-Item Env:ZHANGWEN_DEEPSEEK_API_KEY -ErrorAction SilentlyContinue

    $process = Start-Process -FilePath $sidecarExe -ArgumentList "serve" -PassThru -WindowStyle Hidden
    $baseUrl = "http://127.0.0.1:$port"
    # A clean Windows machine may scan the 800+ MB frozen CAD/runtime payload
    # before Python imports finish. Keep this aligned with the desktop host's
    # finite packaged-Sidecar readiness budget.
    $deadline = (Get-Date).AddSeconds(120)
    do {
        if ($process.HasExited) {
            throw "Packaged Sidecar exited before the health endpoint became ready (exit $($process.ExitCode))."
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
        throw "Packaged Sidecar health endpoint did not become ready."
    }

    $headers = @{
        "X-Zhangwen-Host" = "tauri"
        "X-Zhangwen-Capability-Token" = $token
    }
    $capability = Invoke-RestMethod -Uri "$baseUrl/api/health/desktop-capability" -Headers $headers -TimeoutSec 5
    if ($capability.desktopCapability -ne $true) {
        throw "Packaged Sidecar capability-token validation failed."
    }
    $registration = Invoke-RestMethod `
        -Method Post `
        -Uri "$baseUrl/api/auth/register" `
        -Headers $headers `
        -ContentType "application/json" `
        -Body (@{
            username = "package_smoke"
            displayName = "Package Smoke"
            password = "PackageSmoke123"
        } | ConvertTo-Json) `
        -TimeoutSec 30
    if (-not $registration.sessionToken) {
        throw "Packaged Sidecar did not create a temporary authenticated smoke session."
    }
    $headers["Authorization"] = "Bearer $($registration.sessionToken)"
    $session = Invoke-RestMethod -Uri "$baseUrl/api/auth/session" -Headers $headers -TimeoutSec 5
    if ($session.account.username -ne "package_smoke") {
        throw "Packaged Sidecar authenticated smoke session validation failed."
    }
    $packages = Invoke-RestMethod -Uri "$baseUrl/api/agent-packages" -Headers $headers -TimeoutSec 60
    $profiles = Invoke-RestMethod -Uri "$baseUrl/api/hardware/board-profiles" -Headers $headers -TimeoutSec 60
    $hardware = Invoke-RestMethod -Uri "$baseUrl/api/hardware" -Headers $headers -TimeoutSec 90
    $hardwareSkills = Invoke-RestMethod -Uri "$baseUrl/api/hardware/skills" -Headers $headers -TimeoutSec 90
    $null = Invoke-RestMethod -Uri "$baseUrl/api/projects" -Headers $headers -TimeoutSec 30
    if ($packages.packages.Count -lt 3 -or $profiles.profiles.Count -lt 1) {
        throw "Packaged Agent or BoardProfile resources are incomplete."
    }
    if ($hardware.components.Count -ne $catalogManifest.activeCount -or
        $hardwareSkills.skills.Count -ne $catalogManifest.activeCount) {
        throw "Packaged hardware catalog count does not match its validated manifest."
    }
    $mediaSkill = $hardwareSkills.skills |
        Where-Object { $_.media.Count -gt 0 } |
        Select-Object -First 1
    if (-not $mediaSkill) {
        throw "Packaged hardware catalog has no validated media asset."
    }
    $mediaName = Split-Path -Leaf $mediaSkill.media[0].path
    $mediaResponse = Invoke-WebRequest `
        -Uri "$baseUrl/api/hardware/skills/$($mediaSkill.skillName)/media/$mediaName" `
        -Headers $headers `
        -UseBasicParsing `
        -TimeoutSec 30
    if ($mediaResponse.StatusCode -ne 200 -or $mediaResponse.RawContentLength -lt 1) {
        throw "Packaged hardware media endpoint did not return the bundled asset."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $dataDir "projects\zhangwen.sqlite3") -PathType Leaf)) {
        throw "Packaged Sidecar did not create SQLite in the configured user-data directory."
    }

    foreach ($arguments in @(
        @("context-smoke"),
        @("validation-worker", "static", $workspace),
        @("validation-worker", "syntax", $workspace),
        @("mpremote", "version"),
        @("esptool", "version")
    )) {
        $helper = Start-Process -FilePath $sidecarExe -ArgumentList $arguments -PassThru -Wait -WindowStyle Hidden
        if ($helper.ExitCode -ne 0) {
            throw "Packaged helper '$($arguments[0])' failed with exit code $($helper.ExitCode)."
        }
    }

    Write-Host "Packaged Sidecar smoke test passed without Node.js or Python on PATH." -ForegroundColor Green
}
catch {
    $startupLog = Join-Path $dataDir "logs\sidecar-startup.log"
    if (Test-Path -LiteralPath $startupLog -PathType Leaf) {
        Write-Host "Packaged Sidecar startup diagnostics:" -ForegroundColor Yellow
        Get-Content -Encoding utf8 -LiteralPath $startupLog | Write-Host
    }
    throw
}
finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        $process.WaitForExit(5000) | Out-Null
    }
    foreach ($entry in $saved.GetEnumerator()) {
        Restore-EnvironmentValue -Name $entry.Key -Value $entry.Value
    }
    $resolvedSmokeRoot = [System.IO.Path]::GetFullPath($smokeRoot).TrimEnd('\') + '\'
    $resolvedRunRoot = [System.IO.Path]::GetFullPath($runRoot)
    if ($resolvedRunRoot.StartsWith($resolvedSmokeRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

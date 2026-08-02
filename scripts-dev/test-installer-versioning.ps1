[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "installer-versioning.ps1")

function Assert-Equal {
    param(
        [Parameter(Mandatory = $true)]$Expected,
        [Parameter(Mandatory = $true)]$Actual,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if ($Expected -ne $Actual) {
        throw "$Message Expected '$Expected', received '$Actual'."
    }
}

Assert-Equal "0.1.1" (Get-ZhangwenNextInstallerVersion -Version "0.1.0") "First build version mismatch."
Assert-Equal "0.1.10" (Get-ZhangwenNextInstallerVersion -Version "0.1.9") "Patch rollover mismatch."

$invalidRejected = $false
try {
    $null = Get-ZhangwenNextInstallerVersion -Version "1.0.0"
}
catch {
    $invalidRejected = $true
}
Assert-Equal $true $invalidRejected "Non-0.1.x version was not rejected."

$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
$testRoot = Join-Path $tempBase ("zhangwen-installer-version-test-" + [Guid]::NewGuid().ToString("N"))
$configPath = Join-Path $testRoot "tauri.conf.json"
try {
    New-Item -ItemType Directory -Path $testRoot | Out-Null
    [System.IO.File]::WriteAllText(
        $configPath,
        "{`n  `"productName`": `"掌问`",`n  `"version`": `"0.1.0`",`n  `"marker`": `"preserve-me`"`n}`n",
        [System.Text.UTF8Encoding]::new($false)
    )

    $null = Invoke-ZhangwenInstallerVersionTransaction -ConfigPath $configPath -Action {
        param([string]$Version)
        Assert-Equal "0.1.1" $Version "Transaction supplied the wrong next version."
    }
    Assert-Equal "0.1.1" (Get-ZhangwenTauriVersion -ConfigPath $configPath) "Successful transaction was not retained."
    $configAfterSuccess = Get-Content -Raw -Encoding utf8 -LiteralPath $configPath | ConvertFrom-Json
    Assert-Equal "preserve-me" $configAfterSuccess.marker "Version write changed unrelated config."

    Set-ZhangwenTauriVersion -ConfigPath $configPath -Version "0.1.9"
    $beforeFailure = [System.IO.File]::ReadAllBytes($configPath)
    $failureObserved = $false
    try {
        $null = Invoke-ZhangwenInstallerVersionTransaction -ConfigPath $configPath -Action {
            throw "simulated build failure"
        }
    }
    catch {
        $failureObserved = $true
    }
    Assert-Equal $true $failureObserved "Simulated build failure did not propagate."
    $afterFailure = [System.IO.File]::ReadAllBytes($configPath)
    Assert-Equal ([Convert]::ToBase64String($beforeFailure)) ([Convert]::ToBase64String($afterFailure)) "Failed transaction did not restore the original config bytes."
}
finally {
    $resolvedTestRoot = [System.IO.Path]::GetFullPath($testRoot)
    if ($resolvedTestRoot.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase) -and
        $resolvedTestRoot -ne $tempBase.TrimEnd('\')) {
        Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Installer versioning tests passed." -ForegroundColor Green

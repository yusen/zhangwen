function Get-ZhangwenNextInstallerVersion {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Version
    )

    if ($Version -notmatch '^0\.1\.(\d+)$') {
        throw "Installer version must use the 0.1.x sequence; received '$Version'."
    }

    $patch = [uint64]$Matches[1]
    if ($patch -eq [uint64]::MaxValue) {
        throw "Installer patch version cannot be incremented beyond $patch."
    }
    return "0.1.$($patch + 1)"
}

function Get-ZhangwenTauriVersion {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ConfigPath
    )

    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw "Tauri config not found at $ConfigPath."
    }
    $config = Get-Content -Raw -Encoding utf8 -LiteralPath $ConfigPath | ConvertFrom-Json
    $version = [string]$config.version
    $null = Get-ZhangwenNextInstallerVersion -Version $version
    return $version
}

function Set-ZhangwenTauriVersion {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ConfigPath,
        [Parameter(Mandatory = $true)]
        [string]$Version
    )

    $null = Get-ZhangwenNextInstallerVersion -Version $Version
    $content = [System.IO.File]::ReadAllText($ConfigPath)
    $match = [regex]::Match(
        $content,
        '(?m)^\s*"version"\s*:\s*"(?<version>[^"]+)"'
    )
    if (-not $match.Success) {
        throw "Tauri config does not contain a top-level version field: $ConfigPath"
    }

    $versionGroup = $match.Groups['version']
    $updated = $content.Remove($versionGroup.Index, $versionGroup.Length).Insert(
        $versionGroup.Index,
        $Version
    )
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($ConfigPath, $updated, $utf8NoBom)
}

function Invoke-ZhangwenInstallerVersionTransaction {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ConfigPath,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    $originalBytes = [System.IO.File]::ReadAllBytes($ConfigPath)
    $currentVersion = Get-ZhangwenTauriVersion -ConfigPath $ConfigPath
    $nextVersion = Get-ZhangwenNextInstallerVersion -Version $currentVersion
    $completed = $false
    try {
        Set-ZhangwenTauriVersion -ConfigPath $ConfigPath -Version $nextVersion
        & $Action $nextVersion
        $completed = $true
        return $nextVersion
    }
    finally {
        if (-not $completed) {
            [System.IO.File]::WriteAllBytes($ConfigPath, $originalBytes)
        }
    }
}

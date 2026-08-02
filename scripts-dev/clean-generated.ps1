[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = "Stop"

$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$rootPrefix = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar

$relativeTargets = @(
    ".pnpm-store",
    ".qoder/repowiki",
    "apps/desktop/dist",
    "apps/desktop/src-tauri/gen",
    "apps/desktop/src-tauri/target",
    "packages/contracts/dist",
    "services/local-api/.pytest_cache"
)

$targets = [System.Collections.Generic.List[string]]::new()
foreach ($relativePath in $relativeTargets) {
    $candidate = Join-Path $root $relativePath
    if (Test-Path -LiteralPath $candidate) {
        $targets.Add($candidate)
    }
}

foreach ($searchRoot in @("services/local-api", "scripts")) {
    $absoluteSearchRoot = Join-Path $root $searchRoot
    if (-not (Test-Path -LiteralPath $absoluteSearchRoot)) {
        continue
    }
    Get-ChildItem -LiteralPath $absoluteSearchRoot -Directory -Filter "__pycache__" -Recurse -Force |
        ForEach-Object { $targets.Add($_.FullName) }
}

$uniqueTargets = $targets |
    ForEach-Object { [System.IO.Path]::GetFullPath($_) } |
    Sort-Object -Unique

$removed = 0
[long]$freedBytes = 0
foreach ($candidate in $uniqueTargets) {
    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    if (-not $resolved.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the workspace: $resolved"
    }
    if ($resolved -eq $root) {
        throw "Refusing to remove the workspace root."
    }
    $item = Get-Item -LiteralPath $resolved -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing to recurse through a reparse point: $resolved"
    }

    $size = 0
    if ($item.PSIsContainer) {
        $size = (Get-ChildItem -LiteralPath $resolved -File -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
    }
    elseif ($null -ne $item.Length) {
        $size = $item.Length
    }
    if ($null -eq $size) {
        $size = 0
    }

    if ($PSCmdlet.ShouldProcess($resolved, "Remove generated output")) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
        $removed += 1
        $freedBytes += [long]$size
    }
}

$freedMb = [math]::Round($freedBytes / 1MB, 2)
Write-Output "CLEAN_GENERATED_COMPLETE removed=$removed freedMB=$freedMb"

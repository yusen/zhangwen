[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$serviceRoot = Join-Path $root "services\local-api"
$spec = Join-Path $serviceRoot "zhangwen-sidecar.spec"
$distRoot = Join-Path $root "apps\desktop\src-tauri\resources\sidecar"
$workRoot = Join-Path $root "apps\desktop\src-tauri\target\pyinstaller"
$catalogRoot = Join-Path $serviceRoot ".data\hardware-skills"
$catalogManifest = Join-Path $root "apps\desktop\src-tauri\target\packaging\hardware-catalog-manifest.json"
$expectedVersion = "6.21.0"

if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
    throw "The Zhangwen Sidecar package can only be built on Windows."
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python virtual environment not found at $python."
}
if (-not (Test-Path -LiteralPath $spec -PathType Leaf)) {
    throw "PyInstaller spec not found at $spec."
}

$installedVersion = & $python -c "import PyInstaller; print(PyInstaller.__version__)" 2>$null
if ($LASTEXITCODE -ne 0 -or $installedVersion.Trim() -ne $expectedVersion) {
    throw "PyInstaller $expectedVersion is required. Run: .\.venv\Scripts\python.exe -m pip install -r services\local-api\requirements-build.txt"
}

New-Item -ItemType Directory -Force -Path $distRoot, $workRoot | Out-Null
$previousBytecode = $env:PYTHONDONTWRITEBYTECODE
$previousCatalogManifest = $env:ZHANGWEN_HARDWARE_CATALOG_MANIFEST
$pushedLocation = $false
$env:PYTHONDONTWRITEBYTECODE = "1"
try {
    & $python (Join-Path $root "scripts-dev\verify-bundled-hardware-catalog.py") `
        --source $catalogRoot `
        --output $catalogManifest
    if ($LASTEXITCODE -ne 0) {
        throw "Hardware catalog validation failed with exit code $LASTEXITCODE."
    }
    $env:ZHANGWEN_HARDWARE_CATALOG_MANIFEST = $catalogManifest
    Push-Location $serviceRoot
    $pushedLocation = $true
    & $python -m PyInstaller `
        --clean `
        --noconfirm `
        --distpath $distRoot `
        --workpath $workRoot `
        $spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    if ($pushedLocation) {
        Pop-Location
    }
    $env:PYTHONDONTWRITEBYTECODE = $previousBytecode
    if ($null -eq $previousCatalogManifest) {
        Remove-Item Env:ZHANGWEN_HARDWARE_CATALOG_MANIFEST -ErrorAction SilentlyContinue
    }
    else {
        $env:ZHANGWEN_HARDWARE_CATALOG_MANIFEST = $previousCatalogManifest
    }
}

$sidecarDir = Join-Path $distRoot "zhangwen-sidecar"
$sidecarExe = Join-Path $sidecarDir "zhangwen-sidecar.exe"
if (-not (Test-Path -LiteralPath $sidecarExe -PathType Leaf)) {
    throw "Packaged Sidecar executable was not generated at $sidecarExe."
}

$forbidden = @(
    Get-ChildItem -LiteralPath $sidecarDir -Recurse -Force |
        Where-Object {
            $_.Name -in @(".data", ".env", "zhangwen.sqlite3", "zhangwen.sqlite3-wal", "zhangwen.sqlite3-shm") -or
            $_.FullName -match "[\\/]__pycache__[\\/]" -or
            $_.Extension -in @(".pyc", ".pyo")
        }
)
if ($forbidden.Count -gt 0) {
    throw "Packaged Sidecar contains forbidden generated or user-data files: $($forbidden[0].FullName)"
}

$size = (Get-ChildItem -LiteralPath $sidecarDir -Recurse -File | Measure-Object Length -Sum).Sum
$hash = (Get-FileHash -LiteralPath $sidecarExe -Algorithm SHA256).Hash
Write-Host "Packaged Sidecar ready: $sidecarExe" -ForegroundColor Green
Write-Host "Sidecar payload size: $size bytes; executable SHA256: $hash"

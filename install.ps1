param(
    [string]$InstallDir = ([IO.Path]::Combine([Environment]::GetFolderPath('LocalApplicationData'), 'ZhangWen')),
    [switch]$NoStart,
    [string]$Revision = '',
    [string]$DesktopDir = [Environment]::GetFolderPath('Desktop')
)
$ErrorActionPreference = 'Stop'
$installerModulePath = $env:PSModulePath
try {
    # The remote installer is standalone: isolate before auto-loading any modules.
    # Restore the invoking shell when run with irm | iex or & ./install.ps1.
    $env:PSModulePath = [IO.Path]::Combine($PSHOME, 'Modules')
    $windowsPowerShell = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    if (![Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') { throw 'Windows x64 is required.' }
    $InstallDir = [IO.Path]::GetFullPath($InstallDir)
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    try { $installLock = [IO.File]::Open((Join-Path $InstallDir 'install.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw 'Another installer is running. Please wait for it to finish.' }
    try {
        $headers = @{ 'User-Agent' = 'zhangwen-installer'; 'Accept' = 'application/vnd.github+json' }
        if (!$Revision) { $Revision = (Invoke-RestMethod -Uri 'https://api.github.com/repos/yusen/zhangwen/git/ref/heads/main' -Headers $headers).object.sha }
        if ($Revision -cnotmatch '^[0-9a-f]{40}$') { throw 'Invalid GitHub revision.' }
        $versions = Join-Path $InstallDir 'versions'
        New-Item -ItemType Directory -Force -Path $versions | Out-Null
        $appDir = Join-Path $versions $Revision
        function Test-Package([string]$Directory) {
            $manifest = Join-Path $Directory 'DEPLOYMENT.sha256'
            if (!(Test-Path -LiteralPath $manifest -PathType Leaf)) { return $false }
            $seen = New-Object 'System.Collections.Generic.HashSet[string]'
            foreach ($line in [IO.File]::ReadAllLines($manifest)) {
                if ($line -cnotmatch '^([0-9a-f]{64})  ([A-Za-z0-9_./@+ -]+)$') { return $false }
                $expected = $Matches[1]; $relative = $Matches[2]
                if (!$seen.Add($relative)) { return $false }
                if ($relative.StartsWith('/') -or $relative -match '(^|/)\.\.(/|$)') { return $false }
                $file = Join-Path $Directory $relative
                if (!(Test-Path -LiteralPath $file -PathType Leaf) -or (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $expected) { return $false }
            }
            foreach ($required in @('scripts/bootstrap-windows.ps1', 'scripts/bootstrap-unix.sh', 'package-lock.json', 'services/local-api/zhangwen/web/__main__.py')) {
                if (!$seen.Contains($required)) { return $false }
            }
            return $true
        }
        if (!(Test-Package $appDir)) {
            if (Test-Path -LiteralPath $appDir) { throw 'Existing version has modified or missing files. It was preserved; move it aside before retrying.' }
            $work = Join-Path $InstallDir ('download-' + [guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Path $work | Out-Null
            $zip = Join-Path $work 'source.zip'
            Write-Host "Downloading platform $Revision ..."
            Invoke-WebRequest -UseBasicParsing -Uri "https://codeload.github.com/yusen/zhangwen/zip/$Revision" -OutFile $zip
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $extracted = Join-Path $work 'files'
            New-Item -ItemType Directory -Path $extracted | Out-Null
            $archive = [IO.Compression.ZipFile]::OpenRead($zip)
            try {
                $archiveRoot = $null
                foreach ($entry in $archive.Entries) {
                    if ($entry.FullName -match '(^/|\\|:|(^|/)\.\.(/|$))' -or (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) { throw 'Unsafe archive entry.' }
                    $parts = $entry.FullName -split '/', 2
                    if ($parts.Count -ne 2) { throw 'Unexpected archive layout.' }
                    if (!$archiveRoot) { $archiveRoot = $parts[0] }
                    if ($parts[0] -ne $archiveRoot) { throw 'Archive contains multiple roots.' }
                    if (!$parts[1]) { continue }
                    # Strip GitHub's long root prefix to keep Windows paths short.
                    $target = Join-Path $extracted $parts[1]
                    if ($entry.FullName.EndsWith('/')) { New-Item -ItemType Directory -Force -Path $target | Out-Null }
                    else {
                        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
                        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target)
                    }
                }
            } finally { $archive.Dispose() }
            if (!(Test-Package $extracted)) { throw 'Deployment file verification failed; nothing activated.' }
            Move-Item -LiteralPath $extracted -Destination $appDir
            # Download diagnostics are retained; no recursive deletion of user folders.
        } else { Write-Host 'Platform files are current; skipping source download.' }
        $env:ZHANGWEN_DATA_DIR = Join-Path $InstallDir 'data'
        $env:ZHANGWEN_RUNTIME_DIR = Join-Path $InstallDir 'runtime'
        & $windowsPowerShell -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $appDir 'scripts/bootstrap-windows.ps1') -PrepareOnly
        if ($LASTEXITCODE -ne 0) { throw 'Environment setup failed. The previous version remains selected.' }
        $launcher = Join-Path $InstallDir 'launch.ps1'
        $launcherText = @'
$ErrorActionPreference = 'Stop'
$env:PSModulePath = [IO.Path]::Combine($PSHOME, 'Modules')
$revision = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'current.txt')).Trim()
if ($revision -cnotmatch '^[0-9a-f]{40}$') { throw 'Invalid installed version.' }
$env:ZHANGWEN_DATA_DIR = Join-Path $PSScriptRoot 'data'
$env:ZHANGWEN_RUNTIME_DIR = Join-Path $PSScriptRoot 'runtime'
& (Join-Path $PSScriptRoot "versions/$revision/scripts/bootstrap-windows.ps1")
if ($LASTEXITCODE -ne 0) { Read-Host 'Startup failed. Press Enter to close' }
'@
        [IO.File]::WriteAllText($launcher, $launcherText, (New-Object Text.UTF8Encoding($false)))
        [IO.File]::WriteAllText((Join-Path $InstallDir 'current.txt.tmp'), $Revision)
        Move-Item -LiteralPath (Join-Path $InstallDir 'current.txt.tmp') -Destination (Join-Path $InstallDir 'current.txt') -Force
        & $windowsPowerShell -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $appDir 'scripts/create-shortcut.ps1') -Launcher $launcher -Icon (Join-Path $appDir 'apps/web/src/assets/palm-logo.ico') -Desktop $DesktopDir
        if ($LASTEXITCODE -ne 0) { throw 'Desktop shortcut creation failed; platform files and data were retained.' }
        Write-Host "Installed: $appDir`nData: $env:ZHANGWEN_DATA_DIR"
    } finally { $installLock.Dispose() }
    if (!$NoStart) { & $windowsPowerShell -NoLogo -NoProfile -ExecutionPolicy Bypass -File $launcher }
} finally {
    $env:PSModulePath = $installerModulePath
}

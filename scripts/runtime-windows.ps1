# Runtime probes are offline and bounded; Windows Store aliases are skipped.
function Invoke-RuntimeProbe([string]$Executable, [string]$Arguments) {
    if (!$Executable -or !(Test-Path -LiteralPath $Executable -PathType Leaf)) { return $null }
    if ($Executable -match '\\WindowsApps\\python[^\\]*\.exe$') { return $null }
    $probe = New-Object System.Diagnostics.Process
    $probe.StartInfo.FileName = $Executable
    $probe.StartInfo.Arguments = $Arguments
    $probe.StartInfo.UseShellExecute = $false
    $probe.StartInfo.CreateNoWindow = $true
    $probe.StartInfo.RedirectStandardOutput = $true
    $probe.StartInfo.RedirectStandardError = $true
    try {
        if (!$probe.Start()) { return $null }
        $output = $probe.StandardOutput.ReadToEndAsync()
        $errors = $probe.StandardError.ReadToEndAsync()
        if (!$probe.WaitForExit(8000)) { $probe.Kill(); return $null }
        $probe.WaitForExit()
        if ($probe.ExitCode -ne 0) { return $null }
        return $output.Result.Trim()
    } catch { return $null } finally { $probe.Dispose() }
}

function Get-ApplicationPaths([string[]]$Names) {
    @(foreach ($name in $Names) {
        Get-Command $name -CommandType Application -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }
    }) | Select-Object -Unique
}

function Get-NodeRuntime([string]$Executable) {
    $versionText = Invoke-RuntimeProbe $Executable '--version'
    if (!$versionText -or $versionText -notmatch '^v(\d+)\.\d+\.\d+$' -or [int]$Matches[1] -lt 22) { return $null }
    $npmCandidates = @((Join-Path (Split-Path -Parent $Executable) 'node_modules/npm/bin/npm-cli.js'))
    foreach ($npmCommand in @(Get-ApplicationPaths @('npm.cmd'))) {
        $npmCandidates += Join-Path (Split-Path -Parent $npmCommand) 'node_modules/npm/bin/npm-cli.js'
    }
    foreach ($npmCli in ($npmCandidates | Select-Object -Unique)) {
        if (!(Test-Path -LiteralPath $npmCli -PathType Leaf)) { continue }
        $npmVersion = Invoke-RuntimeProbe $Executable ('"' + $npmCli + '" --version')
        if ($npmVersion -match '^\d+\.\d+\.\d+$') {
            return [pscustomobject]@{ Executable = $Executable; Version = $versionText; NpmCli = $npmCli; NpmVersion = $npmVersion }
        }
    }
    return $null
}

function Get-PythonRuntime([string]$Executable, [string]$Prefix = '') {
    $code = '"import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro); print(sys.executable); print(int(sys.prefix != sys.base_prefix))"'
    $output = Invoke-RuntimeProbe $Executable ($Prefix + ' -c ' + $code)
    if (!$output) { return $null }
    $lines = $output -split '\r?\n'
    if ($lines.Count -ne 3 -or $lines[0] -notmatch '^3 (\d+) (\d+)$' -or [int]$Matches[1] -lt 12) { return $null }
    return [pscustomobject]@{ Executable = $lines[1]; Version = ($lines[0] -replace ' ', '.'); IsVenv = ($lines[2] -eq '1') }
}

function Get-UvRuntime([string[]]$Candidates) {
    foreach ($candidate in ($Candidates | Select-Object -Unique)) {
        $output = Invoke-RuntimeProbe $candidate '--version'
        if ($output -match '^uv (\d+\.\d+\.\d+)' -and [version]$Matches[1] -ge [version]'0.8.22') { return $candidate }
    }
    return $null
}

param(
    [Parameter(Mandatory=$true)][string]$Launcher,
    [Parameter(Mandatory=$true)][string]$Icon,
    [string]$Desktop = [Environment]::GetFolderPath('Desktop')
)
$ErrorActionPreference = 'Stop'
$shortcutModulePath = $env:PSModulePath
try {
    $env:PSModulePath = [IO.Path]::Combine($PSHOME, 'Modules')
    if (!(Test-Path -LiteralPath $Launcher -PathType Leaf) -or !(Test-Path -LiteralPath $Icon -PathType Leaf)) { throw 'Launcher or icon missing.' }
    New-Item -ItemType Directory -Path $Desktop -Force | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    # Keep this script ASCII so Windows PowerShell 5.1 also reads it correctly.
    $displayName = -join @([char]0x638C, [char]0x95EE)
    $shortcutPath = Join-Path $Desktop ($displayName + '.lnk')
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    $shortcut.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + $Launcher + '"'
    $shortcut.WorkingDirectory = Split-Path -Parent $Launcher
    $shortcut.IconLocation = $Icon + ',0'
    $shortcut.Description = $displayName
    $shortcut.WindowStyle = 7
    $shortcut.Save()
    # Retire only the English shortcut pointing to this same managed launcher.
    # A shortcut to another installation or application belongs to the user.
    $legacyPath = Join-Path $Desktop 'ZhangWen.lnk'
    if (Test-Path -LiteralPath $legacyPath -PathType Leaf) {
        $legacy = $shell.CreateShortcut($legacyPath)
        if ($legacy.TargetPath -ieq $shortcut.TargetPath -and $legacy.Arguments -ieq $shortcut.Arguments) {
            Remove-Item -LiteralPath $legacyPath -Force
        }
    }
    Write-Host "Desktop shortcut: $shortcutPath"
} finally {
    $env:PSModulePath = $shortcutModulePath
}

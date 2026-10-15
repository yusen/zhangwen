param(
    [Parameter(Mandatory=$true)][string]$Launcher,
    [Parameter(Mandatory=$true)][string]$Icon,
    [string]$Desktop = [Environment]::GetFolderPath('Desktop')
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $Launcher -PathType Leaf) -or !(Test-Path -LiteralPath $Icon -PathType Leaf)) { throw 'Launcher or icon missing.' }
New-Item -ItemType Directory -Path $Desktop -Force | Out-Null
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $Desktop 'ZhangWen.lnk'))
$shortcut.TargetPath = Join-Path $PSHOME 'powershell.exe'
$shortcut.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + $Launcher + '"'
$shortcut.WorkingDirectory = Split-Path -Parent $Launcher
$shortcut.IconLocation = $Icon + ',0'
$shortcut.Description = 'Start ZhangWen local Web platform'
$shortcut.WindowStyle = 7
$shortcut.Save()
Write-Host "Desktop shortcut: $(Join-Path $Desktop 'ZhangWen.lnk')"

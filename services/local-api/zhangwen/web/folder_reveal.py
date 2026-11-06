"""Fixed Windows Explorer activation; the verified folder path is data on stdin."""
import base64
import json
import subprocess


SCRIPT = r'''
$ErrorActionPreference = 'Stop'
$target = ([Console]::In.ReadToEnd() | ConvertFrom-Json).path
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class FolderWindow {
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr h, int mode);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr p);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
}
'@
$shell = New-Object -ComObject Shell.Application
function Find-FolderWindow {
  foreach ($window in @($shell.Windows())) {
    try {
      if ($window.FullName -notmatch '(?i)[\\/]explorer\.exe$') { continue }
      $folder = $window.Document.Folder.Self.Path
      if ([string]::Equals($folder.TrimEnd('\'), $target.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) { return $window }
    } catch { }
  }
  return $null
}
$found = Find-FolderWindow
if ($null -eq $found) { $shell.Explore($target) }
$deadline = [DateTime]::UtcNow.AddSeconds(6)
while ($null -eq $found -and [DateTime]::UtcNow -lt $deadline) {
  Start-Sleep -Milliseconds 120
  $found = Find-FolderWindow
}
if ($null -eq $found) { throw 'Explorer did not open the target directory' }
$handle = [IntPtr]$found.HWND
$foreground = [FolderWindow]::GetForegroundWindow()
$currentThread = [FolderWindow]::GetCurrentThreadId()
$foregroundThread = [FolderWindow]::GetWindowThreadProcessId($foreground, [IntPtr]::Zero)
$attached = $false
try {
  if ($currentThread -ne $foregroundThread) { $attached = [FolderWindow]::AttachThreadInput($currentThread, $foregroundThread, $true) }
  [void][FolderWindow]::ShowWindowAsync($handle, 9)
  [void][FolderWindow]::SetForegroundWindow($handle)
} finally {
  if ($attached) { [void][FolderWindow]::AttachThreadInput($currentThread, $foregroundThread, $false) }
}
Start-Sleep -Milliseconds 100
if ([FolderWindow]::GetForegroundWindow() -ne $handle) { throw 'Explorer could not be brought to the foreground' }
[Console]::Out.Write('{"foreground":true}')
'''


def reveal(path):
    encoded = base64.b64encode(SCRIPT.encode('utf-16-le')).decode('ascii')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-STA',
                             '-WindowStyle', 'Hidden', '-EncodedCommand', encoded],
                            input=json.dumps({'path': str(path)}, ensure_ascii=True),
                            text=True, capture_output=True, timeout=15, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if json.loads(result.stdout) != {'foreground': True}:
        raise OSError('Explorer activation was not confirmed')

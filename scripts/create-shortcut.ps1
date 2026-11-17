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
    # Use the Unicode Shell link API; WScript.Save can turn this filename into
    # question marks on Windows hosts whose ANSI code page has no Chinese.
    if (!('ZhangWen.Shortcuts.ShellLinkFile' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
namespace ZhangWen.Shortcuts {
    [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
    internal class ShellLink { }
    [ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IShellLinkW {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int count, IntPtr findData, uint flags);
        void GetIDList(out IntPtr item);
        void SetIDList(IntPtr item);
        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder value, int count);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string value);
        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder value, int count);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string value);
        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder value, int count);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string value);
        void GetHotkey(out ushort value);
        void SetHotkey(ushort value);
        void GetShowCmd(out int value);
        void SetShowCmd(int value);
        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int count, out int index);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path, int index);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
        void Resolve(IntPtr window, uint flags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
    }
    public static class ShellLinkFile {
        public static void Save(string path, string target, string arguments, string directory, string icon, string description) {
            object instance = new ShellLink();
            try {
                var link = (IShellLinkW)instance;
                link.SetPath(target);
                link.SetArguments(arguments);
                link.SetWorkingDirectory(directory);
                link.SetIconLocation(icon, 0);
                link.SetDescription(description);
                link.SetShowCmd(7);
                var file = (IPersistFile)instance;
                file.Save(path, true);
                file.SaveCompleted(path);
            } finally { Marshal.FinalReleaseComObject(instance); }
        }
        public static bool Matches(string path, string target, string arguments) {
            object instance = new ShellLink();
            try {
                ((IPersistFile)instance).Load(path, 0);
                var link = (IShellLinkW)instance;
                var savedTarget = new StringBuilder(32768);
                var savedArguments = new StringBuilder(32768);
                link.GetPath(savedTarget, savedTarget.Capacity, IntPtr.Zero, 0);
                link.GetArguments(savedArguments, savedArguments.Capacity);
                return String.Equals(savedTarget.ToString(), target, StringComparison.OrdinalIgnoreCase)
                    && String.Equals(savedArguments.ToString(), arguments, StringComparison.OrdinalIgnoreCase);
            } finally { Marshal.FinalReleaseComObject(instance); }
        }
    }
}
'@
    }
    # Keep this script ASCII so Windows PowerShell 5.1 also reads it correctly.
    $displayName = -join @([char]0x638C, [char]0x95EE)
    $shortcutPath = Join-Path $Desktop ($displayName + '.lnk')
    $target = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    $arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + $Launcher + '"'
    [ZhangWen.Shortcuts.ShellLinkFile]::Save($shortcutPath, $target, $arguments, (Split-Path -Parent $Launcher), $Icon, $displayName)
    # Retire only the English shortcut pointing to this same managed launcher.
    # A shortcut to another installation or application belongs to the user.
    $legacyPath = Join-Path $Desktop 'ZhangWen.lnk'
    if (Test-Path -LiteralPath $legacyPath -PathType Leaf) {
        if ([ZhangWen.Shortcuts.ShellLinkFile]::Matches($legacyPath, $target, $arguments)) {
            Remove-Item -LiteralPath $legacyPath -Force
        }
    }
    Write-Host "Desktop shortcut: $shortcutPath"
} finally {
    $env:PSModulePath = $shortcutModulePath
}

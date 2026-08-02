@echo off
setlocal EnableExtensions DisableDelayedExpansion

cd /d "%~dp0"

if /I "%~1"=="--help" goto :help
if /I "%~1"=="--check" goto :check
if /I "%~1"=="--verify-only" goto :verify
if /I "%~1"=="--install-smoke" goto :install_smoke
if /I "%~1"=="--desktop-smoke" goto :desktop_smoke
if not "%~1"=="" goto :unknown

where pnpm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] pnpm was not found on PATH.
  endlocal & exit /b 1
)

echo Building and verifying the next Zhangwen 0.1.x installer...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts-dev\build-versioned-installer.ps1"
if errorlevel 1 goto :failed

echo.
echo Installer build, verification, and version increment completed.
echo Output: apps\desktop\src-tauri\target\release\bundle\nsis
endlocal & exit /b 0

:verify
call pnpm verify:package:windows
set "exit_code=%ERRORLEVEL%"
endlocal & exit /b %exit_code%

:install_smoke
echo This mode installs and uninstalls the package in an isolated temporary directory.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts-dev\verify-windows-package.ps1" -InstallSmoke
set "exit_code=%ERRORLEVEL%"
endlocal & exit /b %exit_code%

:desktop_smoke
echo This mode starts an isolated installed desktop application and Sidecar.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts-dev\verify-windows-package.ps1" -DesktopSmoke
set "exit_code=%ERRORLEVEL%"
endlocal & exit /b %exit_code%

:check
where pnpm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] pnpm was not found on PATH.
  endlocal & exit /b 1
)
if not exist "%~dp0scripts-dev\build-windows-package.ps1" (
  echo [ERROR] scripts-dev\build-windows-package.ps1 is missing.
  endlocal & exit /b 1
)
if not exist "%~dp0scripts-dev\verify-windows-package.ps1" (
  echo [ERROR] scripts-dev\verify-windows-package.ps1 is missing.
  endlocal & exit /b 1
)
if not exist "%~dp0scripts-dev\build-versioned-installer.ps1" (
  echo [ERROR] scripts-dev\build-versioned-installer.ps1 is missing.
  endlocal & exit /b 1
)
if not exist "%~dp0scripts-dev\installer-versioning.ps1" (
  echo [ERROR] scripts-dev\installer-versioning.ps1 is missing.
  endlocal & exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; @('build-windows-package.ps1','verify-windows-package.ps1','build-versioned-installer.ps1','installer-versioning.ps1','test-installer-versioning.ps1') | ForEach-Object { [scriptblock]::Create((Get-Content -Raw -Encoding UTF8 (Join-Path '%~dp0scripts-dev' $_))) | Out-Null }"
if errorlevel 1 (
  endlocal & exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts-dev\test-installer-versioning.ps1"
if errorlevel 1 (
  endlocal & exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts-dev\build-versioned-installer.ps1" -Check
set "exit_code=%ERRORLEVEL%"
endlocal & exit /b %exit_code%

:unknown
echo [ERROR] Unknown option: %~1
goto :help_error

:failed
set "exit_code=%ERRORLEVEL%"
if "%exit_code%"=="0" set "exit_code=1"
echo.
echo [ERROR] Installer build or verification failed with exit code %exit_code%.
endlocal & exit /b %exit_code%

:help
echo Usage:
echo   build-installer.bat                 Increment 0.1.x, build, and verify the Windows NSIS installer
echo   build-installer.bat --check         Validate prerequisites and script syntax only
echo   build-installer.bat --verify-only   Verify the latest existing installer
echo   build-installer.bat --install-smoke Install/uninstall in an isolated temporary directory
echo   build-installer.bat --desktop-smoke Start an isolated installed desktop smoke test
endlocal & exit /b 0

:help_error
call "%~f0" --help
endlocal & exit /b 2

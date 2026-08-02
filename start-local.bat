@echo off
setlocal

cd /d "%~dp0"

if /I "%~1"=="--help" goto :help
if /I "%~1"=="--check" goto :check

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts-dev\start-local.ps1"
set "exit_code=%ERRORLEVEL%"

endlocal & exit /b %exit_code%

:help
echo Usage:
echo   start-local.bat          Start the complete Zhangwen local app
echo   start-local.bat --check  Validate the local app launcher script
endlocal & exit /b 0

:check
powershell -NoProfile -ExecutionPolicy Bypass -Command "[scriptblock]::Create((Get-Content -Raw -Encoding UTF8 '%~dp0scripts-dev\start-local.ps1')) | Out-Null; Write-Host 'start-local launcher OK'"
set "exit_code=%ERRORLEVEL%"
endlocal & exit /b %exit_code%

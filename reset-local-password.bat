@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo 未找到掌问 Python 环境：.venv\Scripts\python.exe
  echo 请先完成开发环境初始化。
  pause
  exit /b 2
)

".venv\Scripts\python.exe" "scripts-dev\reset-local-account-password.py"
set "ZW_PASSWORD_RESET_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %ZW_PASSWORD_RESET_EXIT%

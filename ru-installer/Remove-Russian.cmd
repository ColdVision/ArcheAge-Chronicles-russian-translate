@echo off
setlocal
chcp 65001 >nul
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\ru-tool.ps1" -Action Remove -GameRoot "%~dp0." %*
set "ru_exit=%errorlevel%"
echo.
pause
exit /b %ru_exit%

@echo off
setlocal

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0gdl_greeting_card_launcher.ps1"
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
    echo ForPrint launcher failed with exit code %RC%.
) else (
    echo ForPrint launcher completed successfully.
)
echo.
pause
exit /b %RC%

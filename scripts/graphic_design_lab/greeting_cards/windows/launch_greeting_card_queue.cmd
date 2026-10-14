@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0gdl_greeting_card_queue.ps1"
if errorlevel 1 (
  echo GC14: Operator review required. Check the output reports or console log.
)
pause

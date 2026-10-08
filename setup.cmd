@echo off
rem One-time setup: downloads the portable Python runtime into runtime\
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
echo.
pause

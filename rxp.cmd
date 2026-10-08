@echo off
setlocal
chcp 65001 >nul

rem Prefer the portable runtime in this folder, fall back to an installed Python.
set "PY=%~dp0runtime\python.exe"
if exist "%PY%" goto run

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo   Python runtime not found.
    echo   Run setup.cmd once to download the portable runtime into runtime\
    echo.
    exit /b 1
)
set "PY=python"

:run
"%PY%" "%~dp0rxp.py" %*

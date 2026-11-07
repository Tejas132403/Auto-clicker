@echo off
setlocal
title Unique Install Task App Installer

:: Change working directory to script directory
cd /d "%~dp0"

:: Detect Python executable
set "PY_EXE="
if exist "%~dp0.venv2\Scripts\python.exe" (
    set "PY_EXE=%~dp0.venv2\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PY_EXE=python"
    ) else (
        where py >nul 2>nul
        if %ERRORLEVEL% equ 0 (
            set "PY_EXE=py"
        )
    )
)

if "%PY_EXE%"=="" (
    echo [ERROR] Python not found! Please check your Python installation.
    pause
    exit /b 1
)

:: Execute the script passing all arguments
"%PY_EXE%" "%~dp0install_unique_app.py" %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo Process completed with errors.
)

pause

@echo off
setlocal enabledelayedexpansion

REM ===========================================================================
REM V2X Sanity Python Environment Setup
REM ===========================================================================

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "REQ_FILE=%SCRIPT_DIR%requirements.txt"
set "PY_CMD="
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

echo.
echo ===========================================================================
echo   V2X Sanity Python Environment Setup
echo ===========================================================================
echo Project: %SCRIPT_DIR%
echo.

REM ------------------ Find Python ------------------
call :FindPython

if not defined PY_CMD (
    echo Python 3.10+ not found. Installing Python 3.12 via winget...
    echo.

    winget --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: winget not available. Install Python manually.
        goto :Fail
    )

    winget install --id Python.Python.3.12 --exact --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 goto :Fail

    call :FindPython
)

if not defined PY_CMD (
    echo ERROR: Python installed but not detected.
    goto :Fail
)

echo Using Python: %PY_CMD%
%PY_CMD% --version || goto :Fail

REM ------------------ Check requirements ------------------
if not exist "%REQ_FILE%" (
    echo ERROR: requirements.txt not found at:
    echo %REQ_FILE%
    goto :Fail
)

REM ------------------ Create venv ------------------
if not exist "%VENV_PY%" (
    echo.
    echo Creating virtual environment...
    %PY_CMD% -m venv "%VENV_DIR%" || goto :Fail
) else (
    echo.
    echo Virtual environment already exists.
)

REM ------------------ Install dependencies ------------------
echo.
echo Upgrading pip...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel || goto :PipFail

echo Removing incorrect 'serial' package...
"%VENV_PY%" -m pip uninstall -y serial >nul 2>&1

echo Installing dependencies from requirements.txt...
"%VENV_PY%" -m pip install -r "%REQ_FILE%" || goto :PipFail

REM ------------------ Verify imports ------------------
echo.
echo Verifying core imports...
"%VENV_PY%" -c "import subprocess, threading, queue, time, datetime, sys, os, json, tempfile, uuid, re, logging, csv, glob; from collections import OrderedDict; from typing import List, Union, Tuple; from datetime import datetime; from queue import Queue, Empty; from pathlib import Path; from fnmatch import fnmatchcase; import serial; from openpyxl import Workbook; print('OK: imports successful')" || goto :Fail

echo Verifying paramiko...
"%VENV_PY%" -c "import paramiko; print('OK: paramiko working')" || goto :Fail

REM ------------------ Create activation script ------------------
echo.
echo Creating activation helper script...

(
echo @echo off
echo set "PROJECT_ROOT=%%~dp0"
echo set "PYTHONPATH=%%PROJECT_ROOT%%;%%PROJECT_ROOT%%tests;%%PROJECT_ROOT%%ExecuteBySSH;%%PYTHONPATH%%"
echo call "%%PROJECT_ROOT%%.venv\Scripts\activate.bat"
echo echo.
echo echo V2X Python environment activated.
) > "%SCRIPT_DIR%activate_project_env.bat"

echo.
echo ===========================================================================
echo   ✅ Setup Completed Successfully
echo ===========================================================================
echo.
echo To activate environment:
echo   activate_project_env.bat
echo.

goto :END

REM ------------------ FUNCTIONS ------------------

:FindPython
set "PY_CMD="

py -3 -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3"
    exit /b
)

python -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
    exit /b
)

exit /b

:PipFail
echo.
echo ERROR: Failed to install Python packages.
goto :Fail

:Fail
echo.
echo ===========================================================================
echo   ❌ Setup Failed
echo ===========================================================================
echo.

REM ------------------ FINAL SAFE EXIT ------------------

:END
echo.
echo Press any key to exit...
pause >nul
endlocal
exit /b
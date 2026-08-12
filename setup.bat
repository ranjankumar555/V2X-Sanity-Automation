@echo off
setlocal enabledelayedexpansion

:: Keep the script working from the project folder even when elevated.
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
cd /d "%SCRIPT_DIR%"

:: Request elevation if not already running as administrator.
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Requesting administrative privileges...
    powershell -NoProfile -Command "Start-Process cmd.exe -ArgumentList '/k cd /d \"%SCRIPT_DIR%\" && \"%SCRIPT_DIR%\setup.bat\"' -Verb RunAs"
    exit /B
)

echo [+] Running with Administrative privileges inside: %SCRIPT_DIR%
echo =================================================================================

set "PYTHON_VER=3.12.4"
set "VENV_DIR=%SCRIPT_DIR%\.venv"
set "INSTALLER=%temp%\python_installer.exe"
set "REQ_FILE=%SCRIPT_DIR%\requirements.txt"
set "PYTHON_CMD="
set "PYTHON_ARGS="

:: Detect Python from PATH or common install locations.
echo [*] Detecting Python...
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=py"
        set "PYTHON_ARGS=-3"
    )
)

if not defined PYTHON_CMD (
    if exist "%ProgramFiles%\Python%PYTHON_VER%\python.exe" (
        set "PYTHON_CMD=%ProgramFiles%\Python%PYTHON_VER%\python.exe"
    )
)
if not defined PYTHON_CMD (
    if exist "%ProgramFiles(x86)%\Python%PYTHON_VER%\python.exe" (
        set "PYTHON_CMD=%ProgramFiles(x86)%\Python%PYTHON_VER%\python.exe"
    )
)
if not defined PYTHON_CMD (
    if exist "%LocalAppData%\Programs\Python\Python%PYTHON_VER%\python.exe" (
        set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python%PYTHON_VER%\python.exe"
    )
)

echo =================================================================================
if defined PYTHON_CMD (
    echo [+] Python command: %PYTHON_CMD% %PYTHON_ARGS%
) else (
    echo [-] Python was not found on PATH or common locations.
    echo [*] Downloading Python %PYTHON_VER%...
    set "ARCH=amd64"
    if "%PROCESSOR_ARCHITECTURE%"=="x86" set "ARCH=win32"
    if "%PROCESSOR_ARCHITEW6432%"=="AMD64" set "ARCH=amd64"
    set "INSTALLER_URL=https://www.python.org/ftp/python/%PYTHON_VER%/python-%PYTHON_VER%-%ARCH%.exe"

    powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%INSTALLER_URL%' -OutFile '%INSTALLER%'"
    if not exist "%INSTALLER%" (
        echo [-] Failed to download Python installer.
        goto End
    )
    echo [*] Installing Python silently...
    start /wait "" "%INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1
    if %errorlevel% neq 0 (
        echo [-] Python installer failed with error %errorlevel%.
        del "%INSTALLER%" 2>nul
        goto End
    )
    del "%INSTALLER%" 2>nul
    set "PYTHON_CMD=python"
)

echo [*] Creating or updating virtual environment...
if exist "%VENV_DIR%" (
    echo [*] Existing virtual environment found at %VENV_DIR%.
) else (
    "%PYTHON_CMD%" %PYTHON_ARGS% -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [-] Failed to create virtual environment.
        goto End
    )
)

set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

echo [*] Upgrading pip inside virtual environment...
"%VENV_PYTHON%" -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo [-] pip upgrade failed.
    goto End
)

if exist "%REQ_FILE%" (
    echo [*] Installing dependencies from requirements.txt...
    "%VENV_PYTHON%" -m pip install -r "%REQ_FILE%"
    if %errorlevel% neq 0 (
        echo [-] Failed to install dependencies from %REQ_FILE%.
        goto End
    )
) else (
    echo [-] requirements.txt not found at %REQ_FILE%.
)

echo [+] Setup complete. The virtual environment is at %VENV_DIR%.
goto End

:End
echo =================================================================================
echo [+] Done.
pause

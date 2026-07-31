@echo off
setlocal enabledelayedexpansion

:: =================================================================================
:: EDGE CASE FIX 3: Capture absolute structural script placement location.
:: If a user calls this remotely from C:\Tools\ while the script lives on D:\, 
:: %~dp0 guarantees we grab the true home directory of the code execution engine.
:: =================================================================================
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

:: Force context switch into the actual repository structure
cd /d "%PROJECT_ROOT%"

:: Replicate precisely what activate_project_env.bat does dynamically using absolute evaluations
set "PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%\tests;%PROJECT_ROOT%\ExecuteBySSH;%PYTHONPATH%"

:: EDGE CASE FIX 4: Check for localized execution assets using absolute paths
if not exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    echo [-] Error: Virtual Environment (.venv) not found at: %PROJECT_ROOT%\.venv
    echo [*] Please run setup.bat first as Administrator to configure this machine.
    echo =================================================================================
    pause
    exit /B
)

echo [+] V2X Sanity Environment Successfully Done.
echo [*] Working Root: %PROJECT_ROOT%
echo [*] Launching basic sanity test suite...
echo =================================================================================

:: Run using the dedicated virtual environment engine explicitly
"%PROJECT_ROOT%\.venv\Scripts\python.exe" test_runner.py --test basic_sanity

echo =================================================================================
echo [+] Test suite run completed.
pause

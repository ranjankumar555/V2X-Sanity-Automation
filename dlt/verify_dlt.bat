@echo off
REM ===========================================================================
REM DLT Verification Batch Script
REM Run DLT verification on test logs and generate summary report
REM ===========================================================================
REM
REM Usage:
REM     verify_dlt.bat                          (uses logs/*.csv files)
REM     verify_dlt.bat <csv_file>               (verify specific file)
REM     verify_dlt.bat <csv_file> <version>    (with device version)
REM
REM Examples:
REM     verify_dlt.bat
REM     verify_dlt.bat ../logs/basic_sanity_dlt.csv "V1.0.0"
REM
REM ===========================================================================

setlocal enabledelayedexpansion

REM Colors for output (using echo with special characters)
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "CYAN=[96m"
set "RESET=[0m"

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=python"

REM Check if Python is available
%PYTHON_EXE% --version >nul 2>&1
if errorlevel 1 (
    echo %RED%Error: Python not found in PATH%RESET%
    echo Please install Python or add it to PATH
    exit /b 1
)

REM Parse arguments
if "%~1"=="" (
    REM No arguments - find all CSV files in parent logs directory
    set "CSV_FILE="
    set "VERSION=1.0.0"
    set "SEARCH_MODE=1"
) else (
    set "CSV_FILE=%~1"
    set "VERSION=%~2"
    if "!VERSION!"=="" set "VERSION=1.0.0"
    set "SEARCH_MODE=0"
)

echo.
echo %CYAN%===========================================================================
echo   DLT LOG VERIFICATION BATCH
echo ===========================================================================
if !SEARCH_MODE!==1 (
    echo Searching for CSV files in ../logs/
) else (
    echo File:    %CSV_FILE%
    echo Version: %VERSION%
)
echo %CYAN%===========================================================================
echo %RESET%

REM Run verification
if !SEARCH_MODE!==1 (
    REM Find and verify all CSV files
    setlocal enabledelayedexpansion
    set "count=0"
    
    for %%F in (%SCRIPT_DIR%..\logs\*.csv) do (
        set /a count+=1
        echo.
        echo Verifying file !count!: %%~nxF
        echo ---
        %PYTHON_EXE% "%SCRIPT_DIR%dlt_quick_verify.py" "%%F" "%VERSION%" --regions EU CN
        
        if errorlevel 1 (
            echo %RED%FAILED: %%~nxF%RESET%
        ) else (
            echo %GREEN%PASSED: %%~nxF%RESET%
        )
    )
    
    if !count!==0 (
        echo %YELLOW%No CSV files found in ../logs/%RESET%
        echo Please export DLT logs to CSV format first
    )
) else (
    REM Verify specific file
    %PYTHON_EXE% "%SCRIPT_DIR%dlt_quick_verify.py" "%CSV_FILE%" "%VERSION%" --regions EU CN
    if errorlevel 1 exit /b 1
)

echo.
echo %CYAN%===========================================================================
echo   Verification Complete
echo ===========================================================================
echo %RESET%
endlocal

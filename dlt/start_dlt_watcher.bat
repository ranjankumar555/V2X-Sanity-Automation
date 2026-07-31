@echo off
REM Auto DLT Processor Start Script
REM Monitors D:\sanity\extract_date\extract_device_variant\ for DLT files

set SCRIPT_DIR=%~dp0
set PYTHON_SCRIPT=%SCRIPT_DIR%dlt_auto_processor.py

echo ========================================
echo DLT Auto Processor Monitor
echo ========================================
echo.
echo Watch Directory: D:\sanity\extract_date\extract_device_variant\
echo Results Directory: D:\sanity\extract_date\extract_device_variant\results\
echo Archive Directory: D:\sanity\extract_date\extract_device_variant\archived\
echo.
echo Expected DLT file pattern: basic_sanity_v040.040.065.iconsf25.oem_260525.dlt
echo.
echo Starting processor... (Press Ctrl+C to stop)
echo ========================================
echo.

python "%PYTHON_SCRIPT%" --watch --interval 5

pause

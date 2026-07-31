@echo off
set "PROJECT_ROOT=%~dp0"
set "PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%tests;%PROJECT_ROOT%ExecuteBySSH;%PYTHONPATH%"
call "%PROJECT_ROOT%.venv\Scripts\activate.bat"
echo.
echo V2X Python environment activated.

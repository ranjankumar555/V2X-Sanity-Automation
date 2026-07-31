@echo off
:: Enable delayed variable expansion to allow variables (like !errorLevel!) to update dynamically inside loops
setlocal enabledelayedexpansion

:: =================================================================================
:: EDGE CASE FIX 1: SYSTEM32 WORKING DIRECTORY JUMP
:: When a batch file is elevated to run as Administrator, Windows automatically jumps 
:: the working directory context to C:\Windows\System32. This breaks any relative pathing.
:: Shifting %~dp0 to a separate variable ensures we lock onto the actual folder where the file lives.
:: =================================================================================
set "SCRIPT_DIR=%~dp0"
:: Strip trailing backslashes if present to prevent malformed double slashes down the line (e.g., D:\path\\tests)
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: Force change drive and directory context back to the true directory of the project files
cd /d "%SCRIPT_DIR%"

:: =================================================================================
:: CENTRAL CONFIGURATION
:: =================================================================================
set "PYTHON_VER=3.12.4"
set "LIBRARIES=paramiko openpyxl pyserial"

:: Dynamic paths computed dynamically relative to this script execution root directory
set "CUSTOM_PATH1=%SCRIPT_DIR%"
set "CUSTOM_PATH=%SCRIPT_DIR%\tests"
set "VENV_DIR=%SCRIPT_DIR%\.venv"
set "INSTALLER=%temp%\python_installer.exe"

:: =================================================================================
:: ENHANCED UAC ELEVATION (Auto Run as Administrator Request)
:: Checks if the terminal currently has permission to query administrative tools.
:: =================================================================================
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :GotAdmin
) else (
    goto :PromptAdmin
)

:PromptAdmin
echo [*] Requesting Administrative privileges...
:: Create a temporary micro-VBScript tool to launch the bypass elevation window
echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"

:: EDGE CASE FIX 2: Explicitly inject the captured absolute SCRIPT_DIR path parameters 
:: into the elevated shell string to prevent the admin shell from waking up inside System32.
echo UAC.ShellExecute "cmd.exe", "/c cd /d ""%SCRIPT_DIR%"" && ""%SCRIPT_DIR%\setup.bat""", "", "runas", 1 >> "%temp%\getadmin.vbs"

:: Run the script to trigger the Windows UAC confirmation dialog prompt box
"%temp%\getadmin.vbs"
del "%temp%\getadmin.vbs"
exit /B

:GotAdmin
:: Re-force working directory focus inside the newly spawned admin shell context
cd /d "%SCRIPT_DIR%"
echo [+] Running with Administrative privileges inside: %SCRIPT_DIR%
echo =================================================================================

:: =================================================================================
:: STEP 1: GLOBAL PYTHON ACCESSIBILITY CHECK
:: Verifies if Python is already configured and reachable inside standard environment paths.
:: =================================================================================
echo [*] Checking for global Python installation...
set "SYS_PYTHON=python"
where python >nul 2>&1
if %errorLevel% == 0 (
    echo [+] Python is already installed globally.
    goto :SetupVenv
)

:: =================================================================================
:: STEP 2: DOWNLOAD & SILENTLY INSTALL PYTHON GLOBALLY
:: Only triggers if 'where python' returns an evaluation error.
:: =================================================================================
echo [-] Python was not found in the system PATH.
echo [*] Determining OS Core Architecture...

:: Inspect system flags to match download payloads to either amd64 or win32 variants
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (set "ARCH=amd64") else if "%PROCESSOR_ARCHITEW6432%"=="AMD64" (set "ARCH=amd64") else (set "ARCH=win32")

:: Fixed URL string back to the official binary executable archive location payload path
set "URL=https://python.org"

echo [*] Downloading Python %PYTHON_VER% (%ARCH%) via PowerShell...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%URL%' -OutFile '%INSTALLER%'"

if not exist "%INSTALLER%" (
    echo [-] Error: Failed to download Python installer payload from repository server.
    goto :End
)

echo [*] Installing Python silently and updating System PATH (Please wait)...
:: InstallAllUsers=1 registers to Program Files. PrependPath=1 pushes location directly to path list.
start /wait "" "%INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1
del "%INSTALLER%"

:: EDGE CASE FIX 3: PARENT TERMINAL STALE VARIABLES BYPASS
:: Windows does not actively push fresh PATH changes to open parent command lines.
:: We manually map the expected global binary location variables for the remaining lifecycle of this script window.
set "ProgramFilesPath=C:\Program Files\Python312"
set "PATH=%ProgramFilesPath%;%ProgramFilesPath%\Scripts;%PATH%"
set "SYS_PYTHON=%ProgramFilesPath%\python.exe"

:: =================================================================================
:: STEP 3: ISOLATED VIRTUAL ENVIRONMENT (.venv) PROVISIONING
:: Isolates project module engines to guarantee zero dependency conflicts with other host software.
:: =================================================================================
:SetupVenv
echo =================================================================================
if exist "%VENV_DIR%" (
    echo [*] Existing virtual environment found at .venv. Skipping initialization, updating dependencies...
) else (
    echo [*] Creating isolated project virtual environment (.venv)...
    "%SYS_PYTHON%" -m venv "%VENV_DIR%"
    if !errorLevel! neq 0 (
        echo [-] Error: Failed to initialize isolated project environment.
        goto :End
    )
)

:: Direct structural location address routing directly targeting our virtualized runtime interpreter
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

:: =================================================================================
:: STEP 4: PACKAGE PIP PIPELINE DEPLOYMENT
:: Packages are loaded safely and exclusively inside our dedicated local virtual folder.
:: =================================================================================
echo [*] Upgrading pip package manager inside virtual environment...
"%VENV_PYTHON%" -m pip install --upgrade pip --quiet

echo [*] Synchronizing required project dependencies: %LIBRARIES%
for %%L in (%LIBRARIES%) do (
    echo [*] Installing dependency module: %%L...
    "%VENV_PYTHON%" -m pip install %%L
)

:: =================================================================================
:: STEP 5: PERMANENT CLOUD PATH REGISTRY WRITING & ACTIVE SYSTEM BROADCAST
:: Writes paths directly into HKEY_LOCAL_MACHINE without making messy duplicate string entries.
:: =================================================================================
echo =================================================================================
echo [*] Registering dynamic project paths to Windows System PATH...
powershell -Command ^
    $paths = @('%CUSTOM_PATH1%', '%CUSTOM_PATH%'); ^
    $regKey = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('SYSTEM\CurrentControlSet\Control\Session Manager\Environment', $true); ^
    $currentPath = $regKey.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames); ^
    $pathList = $currentPath.Split(';', [System.StringSplitOptions]::RemoveEmptyEntries) | ForEach-Object { $_.Trim().TrimEnd('\') }; ^
    $updated = $false; ^
    foreach ($p in $paths) { ^
        $cleanP = $p.Trim().TrimEnd('\'); ^
        if ($pathList -notcontains $cleanP) { ^
            Write-Host '[*] Adding folder to permanent System PATH:' $cleanP; ^
            $currentPath = $currentPath + ';' + $cleanP; ^
            $updated = $true; ^
        } ^
    }; ^
    if ($updated) { ^
        $regKey.SetValue('Path', $currentPath, [Microsoft.Win32.RegistryValueKind]::ExpandString); ^
        $signature = '[DllImport(\"user32.dll\", SetLastError = true, CharSet = CharSet.Auto)] public static extern IntPtr SendMessageW(IntPtr hWnd, uint Msg, IntPtr wParam, string lParam);'; ^
        $type = Add-Type -MemberDefinition $signature -Name 'Win32' -Namespace 'Utils' -PassThru; ^
        [void]$type::SendMessageW([IntPtr]0xFFFF, 0x001A, [IntPtr]0, 'Environment'); ^
    } ^
    $regKey.Close();

:End
echo =================================================================================
echo [+] Setup complete! Your workspace environment is completely ready.
pause

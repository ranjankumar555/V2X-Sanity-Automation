import os
import sys
import platform
import urllib.request
import subprocess
import time

# Configuration
PYTHON_VERSION = "3.12.4"  # Stable Python version
LIBRARIES = ["paramiko", "openpyxl", "pyserial"]

# Dynamic Path Discovery
# os.path.dirname(os.path.abspath(__file__)) gets the folder containing setup.py
BASE_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__)) 
CUSTOM_PATH1 = BASE_PROJECT_DIR
CUSTOM_PATH = os.path.join(BASE_PROJECT_DIR, "tests")

def is_admin():
    """Checks if the script is running with administrative privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def get_python_download_url():
    """Determines Windows OS architecture and returns the matching official download URL."""
    is_64bit = platform.machine().endswith('64') or os.environ.get('PROCESSOR_ARCHITECTURE') == 'AMD64'
    arch = "amd64" if is_64bit else "win32"
    url = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-{arch}.exe"
    return url

def download_installer(url, dest_path):
    """Downloads the official executable installer payload from Python.org."""
    print(f"[*] Downloading Python {PYTHON_VERSION} installer...")
    try:
        urllib.request.urlretrieve(url, dest_path)
        print("[+] Download complete.")
    except Exception as e:
        print(f"[-] Failed to download installer: {e}")
        sys.exit(1)

def install_python(installer_path):
    """Executes a quiet, silent install that automatically registers environment variables."""
    print("[*] Installing Python silently (this will take a minute)...")
    args = [
        installer_path, 
        "/quiet", 
        "InstallAllUsers=1", 
        "PrependPath=1", 
        "Include_pip=1"
    ]
    
    try:
        subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("[+] Python installed successfully and added to PATH variables.")
    except subprocess.CalledProcessError as e:
        print(f"[-] Installation failed with error code {e.returncode}")
        print(e.stderr.decode())
        sys.exit(1)

def update_local_path():
    """Finds the fresh Python files and injects them into the current running process path."""
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    py_dir_name = f"Python{ ''.join(PYTHON_VERSION.split('.')[:2]) }"
    
    base_path = os.path.join(program_files, py_dir_name)
    scripts_path = os.path.join(base_path, "Scripts")
    
    if os.path.exists(base_path):
        os.environ["PATH"] = f"{base_path};{scripts_path};{os.environ['PATH']}"
        return os.path.join(base_path, "python.exe")
    
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    base_path_user = os.path.join(local_appdata, "Programs", "Python", py_dir_name)
    scripts_path_user = os.path.join(base_path_user, "Scripts")
    
    if os.path.exists(base_path_user):
        os.environ["PATH"] = f"{base_path_user};{scripts_path_user};{os.environ['PATH']}"
        return os.path.join(base_path_user, "python.exe")
        
    return "python"

def install_libraries(python_executable):
    """Invokes pip to safely install required project libraries."""
    print(f"[*] Upgrading pip and installing required dependencies: {', '.join(LIBRARIES)}")
    subprocess.run([python_executable, "-m", "pip", "install", "--upgrade", "pip"], check=False)
    
    for lib in LIBRARIES:
        print(f"[*] Installing {lib}...")
        try:
            subprocess.run([python_executable, "-m", "pip", "install", lib], check=True)
            print(f"[+] Successfully installed {lib}")
        except subprocess.CalledProcessError:
            print(f"[-] Failed to install {lib}")

def add_custom_path_to_system(path_to_add):
    """Permanently adds a custom folder directory to the Windows System PATH environment variables."""
    print(f"[*] Checking System PATH for: {path_to_add}")
    import winreg
    
    try:
        # Open the Windows Registry key for System Environment Variables
        reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", 0, winreg.KEY_ALL_ACCESS)
        
        # Read the current System PATH value
        current_path, data_type = winreg.QueryValueEx(reg_key, "Path")
        
        # Split current path to avoid duplicates
        path_list = [p.strip().rstrip('\\') for p in current_path.split(';') if p.strip()]
        cleaned_target = path_to_add.strip().rstrip('\\')
        
        if cleaned_target not in path_list:
            print("[*] Adding target folder to permanent System PATH...")
            new_path = f"{current_path};{cleaned_target}"
            winreg.SetValueEx(reg_key, "Path", 0, data_type, new_path)
            winreg.CloseKey(reg_key)
            
            # Broadcast settings change to the OS so team members do not need to restart their PC
            import ctypes
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment")
            print("[+] Successfully added custom folder to System PATH.")
        else:
            print("[─] Target folder path is already registered in System PATH.")
            winreg.CloseKey(reg_key)
            
    except Exception as e:
        print(f"[-] Failed to modify System PATH Registry: {e}")

def main():
    if sys.platform != "win32":
        print("[-] This bootstrap configuration script is built specifically for Windows operating systems.")
        sys.exit(1)
        
    if not is_admin():
        print("[-] Error: Administrative privileges are required to edit global environment variables.")
        print("[*] Please relaunch your command line shell by choosing 'Run as Administrator'.")
        sys.exit(1)

    installer_filename = "python_installer.exe"
    download_url = get_python_download_url()
    
    # Run pipelines
    download_installer(download_url, installer_filename)
    install_python(installer_filename)
    
    if os.path.exists(installer_filename):
        os.remove(installer_filename)
        
    target_python = update_local_path()
    install_libraries(target_python)
    
    # Inject your custom tests folder pathway into the machine's Environment
    add_custom_path_to_system(CUSTOM_PATH)
    add_custom_path_to_system(CUSTOM_PATH1)
    
    print("\n[+] Setup complete! Python, libraries, and custom script commands are ready to go.")
    print("[*] IMPORTANT: Your team members must open a FRESH command line terminal to use the new settings.")

if __name__ == "__main__":
    main()

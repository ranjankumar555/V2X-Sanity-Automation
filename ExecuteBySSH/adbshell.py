import subprocess
import threading
import queue
import time
import datetime
import sys
import os
import json
import tempfile
import json
import re
from collections import OrderedDict
# ------------------------------
# Logger
# ------------------------------
class ADBLogger:
    def __init__(self, log_file=None):
        self.log_file = log_file

    def log(self, message):
        """Write normal messages to stdout and log file."""
        if message is None:
            return
        sys.stdout.write(message + "\n")
        sys.stdout.flush()
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")

    def log_error(self, message):
        """Write error messages to stderr and log file."""
        if message is None:
            return
        sys.stderr.write(message + "\n")
        sys.stderr.flush()
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")

# ------------------------------
# Shell (persistent session)
# ------------------------------
class ADBShell:
    def __init__(self, adb_cmd="shell", logger=None, reconnect_attempts=3, reconnect_delay=5):
        self.adb_cmd = adb_cmd
        self.logger = logger or ADBLogger()
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay

        self._start_shell()

    def _start_shell(self):
        """Start persistent shell and reader thread."""
        self.logger.log("=== Starting ADB Shell ===")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{timestamp}]"
        self.logger.log(full_message)
        subprocess.run([self.adb_cmd, "wait-for-device", "root"], check=True)
        time.sleep(1)

        self.proc = subprocess.Popen(
            [self.adb_cmd, "shell"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        self.q = queue.Queue()
        self.reader_thread = threading.Thread(target=self._enqueue_output, daemon=True)
        self.reader_thread.start()

    def _enqueue_output(self):
        """Continuously enqueue stdout lines."""
        for line in self.proc.stdout:
            self.q.put(line)

    def _reconnect_if_needed(self):
        """Check if shell is alive; reconnect if not."""
        if self.proc.poll() is None:
            return
        self.logger.log_error("[WARN] Shell lost. Attempting to reconnect...")
        for attempt in range(1, self.reconnect_attempts + 1):
            try:
                self._start_shell()
                self.logger.log(f"[INFO] Reconnected shell (attempt {attempt})")
                return
            except Exception as e:
                self.logger.log_error(f"[WARN] Reconnect attempt {attempt} failed: {e}")
                time.sleep(self.reconnect_delay)
        raise RuntimeError("Could not reconnect to ADB shell after device reboot.")


    # def run(self, command, timeout=10):
    #     """Run a command in the persistent ADB shell; capture all output (stdout+stderr)."""
    #     self._reconnect_if_needed()
    #     self.logger.log(f"{command}")

    #     # Send command
    #     if self.proc.stdin:
    #         self.proc.stdin.write(f"{command}\n")
    #         self.proc.stdin.flush()

    #     output_lines = []
    #     start_time = time.time()
    #     shell_prompt_pattern = re.compile(r"^(.*[#\$] )$")  # captures shell prompt endings

    #     while True:
    #         try:
    #             line = self.q.get(timeout=timeout)
    #         except queue.Empty:
    #             break

    #         # Clean up line endings
    #         line = line.rstrip("\r\n")
    #         output_lines.append(line)

    #         # Log every line to both console and file
    #         self.logger.log(line)

    #         # Detect prompt -> command finished
    #         if shell_prompt_pattern.match(line.strip()) and (time.time() - start_time > 0.2):
    #             break

    #     return "\n".join(output_lines)
    
    def run(self, command, timeout=10):
        """Run a command in the persistent ADB shell; capture all output (stdout+stderr)."""
        self._reconnect_if_needed()
        
        # Log the command being executed
        # self.logger.log(f">>> {command}")  

        # Send command to shell
        if self.proc.stdin:
            self.proc.stdin.write(f"{command}\n")
            self.proc.stdin.flush()

        output_lines = []
        start_time = time.time()
        shell_prompt_pattern = re.compile(r"^(.*[#\$] )$")  # detects shell prompt endings

        while True:
            try:
                line = self.q.get(timeout=timeout)
            except queue.Empty:
                break

            line = line.rstrip("\r\n")
            output_lines.append(line)

            # Log output line to file
            self.logger.log(line)

            # Stop reading if shell prompt is detected (and command has run for at least 0.2s)
            if shell_prompt_pattern.match(line.strip()) and (time.time() - start_time > 0.2):
                break

        output_str = "\n".join(output_lines)

        return output_str


    def run_batch(self, commands, default_delay=0):
        for item in commands:
            if isinstance(item, tuple):
                cmd, delay = item
            else:
                cmd, delay = item, default_delay
            self.run(cmd)
            time.sleep(delay)

    def close(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.write("exit\n")
                self.proc.stdin.flush()
                self.proc.terminate()
            except Exception:
                pass
        self.logger.log("=== ADB Shell Closed ===")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{timestamp}]"
        self.logger.log(full_message)


# ------------------------------
# File Manager
# ------------------------------
class ADBFileManager:
    def __init__(self, adb_cmd="shell", logger=None):
        self.adb_cmd = adb_cmd
        self.logger = logger or ADBLogger()

    def push(self, local_path, remote_path, force=False):
        try:
            # Compute target path inside remote folder
            # base_name = os.path.basename(local_path.rstrip('/\\'))
            # remote_target = os.path.join(remote_path.rstrip('/'), base_name)

            # # Check if target already exists
            # result = subprocess.run(
            #     [self.adb_cmd, "shell", f"ls {remote_target}"],
            #     capture_output=True, text=True
            # )
            # file_exists = "No such file" not in result.stderr

            # if file_exists and not force:
            #     self.logger.log(f"[SKIP] {remote_target} already present.")
            #     return

            # Perform push
            subprocess.run([self.adb_cmd, "push", local_path, remote_path], check=True, text=True)
            self.logger.log(f"[OK] Pushed {local_path} → {remote_path}")
        except subprocess.CalledProcessError as e:
            self.logger.log_error(f"Failed to push {local_path}: {e}")


    def pull(self, remote_path, local_path):
        try:
            subprocess.run([self.adb_cmd, "pull", remote_path, local_path], check=True, text=True)
            self.logger.log(f"[OK] Pulled {remote_path} → {local_path}")
        except subprocess.CalledProcessError as e:
            self.logger.log_error(f"Failed to pull {remote_path}: {e}")

    def push_folder(self, local_folder, remote_folder):
        if not os.path.isdir(local_folder):
            self.logger.log_error(f"{local_folder} is not a directory")
            return

        for filename in os.listdir(local_folder):
            local_path = os.path.join(local_folder, filename)
            remote_path = f"{remote_folder.rstrip('/')}/{filename}"  # ✅ POSIX-style

            if os.path.isfile(local_path):
                self.push(local_path, remote_path)


# ------------------------------
# Helper Function
# ------------------------------
class Helper:
    @staticmethod
    def ask(prompt):
        """Prompt user with Y/N question and return True/False."""
        while True:
            answer = input(prompt + " [Y/N]: ").strip().upper()
            if answer == "Y":
                return True
            elif answer == "N":
                print("Please complete the required step before continuing...")
            else:
                print("Invalid input. Please type Y or N.")

    @staticmethod
    def is_stack_on(shell, logger=None, min_lines=5, max_attempts=5, delay_between=5):
        """
        Automatically check if the stack is ON using 'unplugged-rt-status-gen'.
        Accepts either ``is_stack_on(shell, logger)`` or the older
        ``is_stack_on(shell, min_lines, max_attempts, delay_between)`` form.
        """
        if isinstance(logger, int):
            delay_between = max_attempts
            max_attempts = min_lines
            min_lines = logger
            logger = None

        log = logger.log if hasattr(logger, "log") else print
        log_error = logger.log_error if hasattr(logger, "log_error") else print

        for attempt in range(1, max_attempts + 1):
            log(f"[Stack Check] Attempt {attempt}...")
            output = shell.run("unplugged-rt-status-gen", timeout=10)
            line_count = len(output.strip().splitlines())
            log(f"Lines in output: {line_count}")
            if line_count > min_lines:
                log("[Stack Check] Stack is ON")
                return
            if attempt < max_attempts:
                log(f"Stack still OFF. Waiting {delay_between}s before retry...")
                time.sleep(delay_between)

        log_error("[Stack Check] Stack not ON after maximum attempts. Exiting...")
        sys.exit(1)

    @staticmethod
    def is_region_eu(file, remote_path="/etc/its.json", local_dir=r"D:\Help\automation"):
        """
        Pulls its.json from remote device and checks if region is EU or CN.
        """

        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, "its.json")

        # 1. Pull the file from device
        print(f"[INFO] Pulling {remote_path} → {local_path}")
        file.pull(remote_path, local_path)

        if not os.path.exists(local_path):
            print(f"❌ Pull failed — file not found at {local_path}")
            return None

        # 2. Load JSON
        with open(local_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 3. Check region
        security = data.get("security", {})
        directories = security.get("directories", {})

        if "eu" in directories:
            print("Region is EU")
            print(f"EU directory path: {directories['eu']}")
            return True
        elif "cn" in directories:
            print("Region is CN")
            print(f"CN directory path: {directories['cn']}")
            return False
        else:
            print("Region not found in security.directories")
            return None


    def modify_its_json(shell, file, remote_path="/etc/its.json"):
        """
        Pulls its.json from the remote device, modifies it locally, and pushes it back.
        """

        # --- 1. Backup existing JSON file on target ---
        local_dir = r"D:\Help\automation"
        backup_path = local_dir + ".bak"
        print(f"[INFO] Creating backup on device: {backup_path}")
        shell.run(f"cp {remote_path} {backup_path}")

        # --- 2. Pull file to local machine ---
        
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, "its.json")

        print(f"[INFO] Pulling {remote_path} → {local_path}")
        file.pull(remote_path, local_path)

        if not os.path.exists(local_path):
            print(f"❌ Pull failed — file not found at {local_path}")
            return

        # --- 3. Load JSON preserving order ---
        with open(local_path, "r", encoding="utf-8") as f:
            data = json.load(f, object_pairs_hook=OrderedDict)

        # --- 4. Modify 'security' section ---
        if "security" in data:
            sec = data["security"]
            sec["enable"] = "Yes"
            sec["checkCrl"] = "Permissive"
            sec["checkLoadedCertificates"] = False

            # Region-based directories
            if "directories" in sec:
                dirs = sec["directories"]
                if "eu" in dirs:
                    dirs["eu"] = "/data/v2xmgr/etc/MBD"
                else:
                    sec["directories"] = {
                        "cn": "/data/v2xmgr/etc/test_certs/security_cn"
                    }

            # Insert checkTimestamp after checkLoadedCertificates
            new_sec = OrderedDict()
            for key, value in sec.items():
                new_sec[key] = value
                if key == "checkLoadedCertificates":
                    new_sec["checkTimestamp"] = False
            data["security"] = new_sec

        # --- 5. Insert 'logging' after 'security' ---
        new_data = OrderedDict()
        for key, value in data.items():
            new_data[key] = value
            if key == "security":
                new_data["logging"] = OrderedDict([
                    ("logLevel", "Debug"),
                    ("debugComponents", ["SEC"])
                ])

        # --- 6. Modify 'hsm' ---
        if "hsm" in new_data:
            new_data["hsm"] = {"type": "Emulated"}

        # --- 7. Disable geofencing ---
        if "geofencing" in new_data:
            new_data["geofencing"]["enable"] = False

        # --- 8. Write modified JSON back ---
        json_str = json.dumps(new_data, indent=2, separators=(",", ": "))
        json_str = re.sub(r'\[\s*"SEC"\s*\]', '["SEC"]', json_str)

        with open(local_path, "w", encoding="utf-8") as f:
            f.write(json_str)

        print(f"[INFO] Local file modified successfully → {local_path}")

        # --- 9. Push file back to remote device ---
        file.push(local_path, remote_path, force=True)
        print(f"[OK] Modified its.json pushed → {remote_path}")
        print(f"[INFO] Backup retained at {backup_path}")

    def is_icon_sf25(version_output: str) -> bool:
        """Return True if 'iconsf25' is found in the version output."""
        if version_output is None:
            return False
        return "iconsf25" in version_output.lower()  # lowercase to make it case-insensitive


#!/usr/bin/env python3
r"""
Cybersecurity Test Runner over SSH (single persistent session)

- Converts your ADB-based flow to SSH using Paramiko.
- Keeps ONE interactive bash shell open for all commands.
- Provides SSH equivalents of ADBShell, ADBFileManager, ADBLogger, and Helper.
- Implements Helper.ask (Y/N), Helper.is_stack_on (unplugged-rt-status-gen),
  Helper.is_region_eu (pull its.json and check security.directories),
  Helper.modify_its_json (backup, local modify preserving order, push back),
  Helper.is_icon_sf25.

Run (PowerShell):
  pip install paramiko
  python .\ssh_cybersecurity_test.py
"""

import os
import sys
import time
import json
import shlex
import posixpath
import re
import shutil
from collections import OrderedDict
from datetime import datetime
from typing import List, Tuple, Union, Optional
from adbshell import Helper1
# ----------------------------- Paramiko import -----------------------------
try:
    import paramiko
except ImportError:
    print("ERROR: This script requires the 'paramiko' package. Install it with: pip install paramiko", file=sys.stderr)
    sys.exit(1)


# ============================= Logger ======================================
class Logger:
    def __init__(self, log_file: str):
        self.log_file = log_file
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        except Exception:
            pass
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{ts}] Log started\n")
        except Exception as e:
            print(f"WARN: Unable to open log file {self.log_file}: {e}")

    def _ts(self) -> str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def log(self, msg: str):
        line = f"[{self._ts()}] {msg}"
        print(line)
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(line + "\n")
        except Exception:
            pass

    def log_error(self, msg: str):
        self.log(f"ERROR: {msg}")


# ============================= SSH Session =================================
class SSHSession:
    """
    Owns the Paramiko SSHClient and provides:
      - a single interactive bash shell channel
      - an SFTP client for file transfers
    """
    def __init__(self, host: str, user: str, key_file: Optional[str], logger: Logger,
                 password: Optional[str] = None, accept_host_key: bool = True):
        self.host = host
        self.user = user
        self.key_file = key_file
        self.password = password
        self.accept_host_key = accept_host_key
        self.logger = logger

        self.client: Optional[paramiko.SSHClient] = None
        self.chan: Optional[paramiko.Channel] = None
        self.sftp: Optional[paramiko.SFTPClient] = None

    def connect(self):
        self.client = paramiko.SSHClient()
        if self.accept_host_key:
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        else:
            self.client.set_missing_host_key_policy(paramiko.RejectPolicy())

        self.logger.log(f"Connecting to {self.user}@{self.host} ...")
        self.client.connect(
            hostname=self.host,
            username=self.user,
            key_filename=self.key_file,
            password=self.password,
            allow_agent=True,
            look_for_keys=True,
            timeout=20,
        )
        self.logger.log("SSH connected.")

        # Open single interactive bash login shell
        self.chan = self.client.invoke_shell(width=200, height=50)
        self.chan.send("bash -li\n")
        time.sleep(0.8)
        self._drain_channel(self.chan, idle_window=0.25)

        # Open an SFTP session
        self.sftp = self.client.open_sftp()

    def close(self):
        try:
            if self.sftp:
                self.sftp.close()
        except Exception:
            pass
        try:
            if self.chan:
                self.chan.close()
        except Exception:
            pass
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass
        self.logger.log("SSH session closed.")

    @staticmethod
    def _drain_channel(chan: paramiko.Channel, idle_window: float = 0.20) -> str:
        """Read available data from channel until idle for idle_window seconds."""
        buf = []
        last = time.time()
        while True:
            if chan.recv_ready():
                data = chan.recv(4096)
                if not data:
                    break
                buf.append(data.decode(errors='ignore'))
                last = time.time()
            else:
                if time.time() - last > idle_window:
                    break
                time.sleep(0.05)
        return ''.join(buf)


# ============================= SSH Shell ===================================
class SSHShell:
    """
    SSH-backed shell API compatible with your ADBShell usage:
      - run(cmd, timeout=60)  -> returns stdout
      - run_batch(commands, default_delay=2, default_timeout=60)
    Internally uses ONE interactive shell channel from SSHSession.
    """
    def __init__(self, session: SSHSession, logger: Logger):
        self.session = session
        self.logger = logger
        if not self.session.chan:
            raise RuntimeError("SSHSession channel not initialized. Call session.connect() first.")

    def run(self, command: str, timeout: int = 60) -> str:
        """
        Run command inside ONE persistent shell:
          Send: bash -lc '<quoted>'; echo __RC__$?
          Parse __RC__ marker to get the numeric exit code.
        """
        quoted = shlex.quote(command)
        marked = f"bash -lc {quoted}; echo __RC__$?\n"
        self.logger.log(f"SHELL: {command}")
        self.session.chan.send(marked)

        start = time.time()
        output = ''
        rc = None

        while True:
            chunk = self.session._drain_channel(self.session.chan, idle_window=0.25)
            if chunk:
                output += chunk
                if "__RC__" in output:
                    lines = output.strip().splitlines()
                    for i in range(len(lines) - 1, -1, -1):
                        if lines[i].startswith("__RC__"):
                            try:
                                rc = int(lines[i].split('__RC__')[-1])
                            except Exception:
                                rc = None
                            output = '\n'.join(l for idx, l in enumerate(lines) if idx != i)
                            break
            if rc is not None:
                break
            if time.time() - start > timeout:
                self.logger.log(f"Timeout after {timeout}s for command: {command}")
                rc = 124
                break
            time.sleep(0.05)

        out = output.strip()
        if out:
            print(out)
        self.logger.log(f"Exit code: {rc}\n")
        return out

    def run_batch(self, commands: List[Union[str, Tuple]], default_delay: int = 2, default_timeout: int = 60):
        """
        Run a list of commands.
        - str: command (delay defaults to default_delay)
        - tuple: (cmd, delay) or (cmd, delay, timeout)
        """
        for item in commands:
            if isinstance(item, tuple):
                cmd = item[0]
                delay = int(item[1]) if len(item) > 1 else default_delay
                timeout = int(item[2]) if len(item) > 2 else default_timeout
            else:
                cmd = str(item)
                delay = default_delay
                timeout = default_timeout

            self.run(cmd, timeout=timeout)
            if delay > 0:
                self.logger.log(f"Sleeping {delay}s...")
                time.sleep(delay)


# =========================== SSH File Manager ===============================
class SSHFileManager:
    """
    SSH-backed file manager compatible with your ADBFileManager usage:
      - push_folder(local_dir, remote_dir)
      - pull(remote_path, local_path)
      - push(local_path, remote_path, force=True)
      - read_text(remote_path)
      - write_text(remote_path, text)
      - chmod(remote_path, mode)
      - exists(remote_path)
      - list_dir(remote_dir)
    Uses the same SSHSession (SFTP client).
    """
    def __init__(self, session: SSHSession, logger: Logger):
        self.session = session
        self.logger = logger
        if not self.session.sftp:
            raise RuntimeError("SSHSession SFTP not initialized. Call session.connect() first.")

    # ---------- Path helpers ----------
    @staticmethod
    def _rjoin(*parts) -> str:
        path = posixpath.join(*parts)
        path = posixpath.normpath(path).replace('\\', '/')
        return path

    def exists(self, remote_path: str) -> bool:
        try:
            self.session.sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False
        except IOError:
            return False

    def mkdirs(self, remote_dir: str):
        remote_dir = remote_dir.strip('/')
        if not remote_dir:
            return
        current = ''
        for part in remote_dir.split('/'):
            current = current + '/' + part if current else '/' + part
            try:
                self.session.sftp.stat(current)
            except FileNotFoundError:
                self.logger.log(f"mkdir {current}")
                self.session.sftp.mkdir(current)
            except Exception:
                pass

    def push_folder(self, local_dir: str, remote_dir: str):
        if not os.path.isdir(local_dir):
            self.logger.log_error(f"Local folder not found: {local_dir}")
            return
        self.mkdirs(remote_dir)
        for root, _, files in os.walk(local_dir):
            rel = os.path.relpath(root, local_dir)
            subdir = '' if rel == '.' else rel.replace('\\', '/')
            target_dir = self._rjoin(remote_dir, subdir) if subdir else remote_dir
            self.mkdirs(target_dir)
            for fname in files:
                lpath = os.path.join(root, fname)
                rpath = self._rjoin(target_dir, fname)
                self.logger.log(f"PUT {lpath} -> {rpath}")
                self.session.sftp.put(lpath, rpath)

    def pull(self, remote_path: str, local_path: str):
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self.logger.log(f"GET {remote_path} -> {local_path}")
        self.session.sftp.get(remote_path, local_path)

    def push(self, local_path: str, remote_path: str, force: bool = True):
        self.mkdirs(posixpath.dirname(remote_path))
        self.logger.log(f"PUT {local_path} -> {remote_path}")
        self.session.sftp.put(local_path, remote_path)

    def read_text(self, remote_path: str, encoding: str = 'utf-8') -> str:
        with self.session.sftp.open(remote_path, 'r') as f:
            data = f.read()
            if isinstance(data, bytes):
                return data.decode(encoding, errors='ignore')
            return data

    def write_text(self, remote_path: str, text: str, encoding: str = 'utf-8'):
        tmp_dir = posixpath.dirname(remote_path)
        self.mkdirs(tmp_dir if tmp_dir else '/')
        with self.session.sftp.open(remote_path, 'w') as f:
            if isinstance(text, str):
                f.write(text)
            else:
                f.write(text.decode(encoding, errors='ignore'))

    def chmod(self, remote_path: str, mode: int):
        try:
            self.session.sftp.chmod(remote_path, mode)
            self.logger.log(f"chmod {oct(mode)} {remote_path}")
        except Exception as e:
            self.logger.log_error(f"chmod failed for {remote_path}: {e}")

    def list_dir(self, remote_dir: str) -> List[str]:
        try:
            return self.session.sftp.listdir(remote_dir)
        except Exception as e:
            self.logger.log_error(f"list_dir failed for {remote_dir}: {e}")
            return []


# ================================ Helper() ====================================

# imports needed by Helper
import os, sys, time, json, shlex, re
from collections import OrderedDict
from typing import Optional, List, Tuple, Union

class Helper:
    def __init__(self, logger: Logger):
        self.logger = logger

    def ask(self, prompt: str) -> bool:
        """Prompt user with Y/N question and return True/False (waits until Y)."""
        # Log the question; input() shows the same prompt text to user
        self.logger.log(f"[QUESTION] {prompt}")
        while True:
            try:
                answer = input(prompt + " [Y/N]: ").strip().upper()
            except EOFError:
                # Non-interactive environment: assume 'Y' to continue
                self.logger.log("[QUESTION] Non-interactive environment → continuing (Y).")
                return True
            if answer == 'Y':
                self.logger.log("[QUESTION] Answer = Y")
                return True
            elif answer == 'N':
                self.logger.log("[QUESTION] Answer = N → user will complete step before continuing...")
            else:
                self.logger.log_error("Invalid input. Please type Y or N.")

    def is_stack_on(self,
                    shell: SSHShell,
                    min_lines: int = 5,
                    max_attempts: int = 5,
                    delay_between: int = 5) -> bool:
        """
        Automatically check if the stack is ON using 'unplugged-rt-status-gen'.
        If stack does not turn ON after max_attempts, halts the script.
        """
        for attempt in range(1, max_attempts + 1):
            self.logger.log(f"[Stack Check] Attempt {attempt}...")
            output = shell.run("unplugged-rt-status-gen", timeout=10)
            line_count = len(output.strip().splitlines()) if output else 0
            self.logger.log(f"[Stack Check] Lines in output: {line_count}")
            if line_count > min_lines:
                self.logger.log("[Stack Check] Stack is ON")
                return True
            if attempt < max_attempts:
                self.logger.log(f"[Stack Check] Stack still OFF. Waiting {delay_between}s before retry...")
                time.sleep(delay_between)
        self.logger.log_error("[Stack Check] Stack not ON after maximum attempts. Exiting...")
        sys.exit(1)

    def modify_its_json(self,
                    shell: SSHShell,
                    files: SSHFileManager,
                    remote_path: str = "/etc/its.json",
                    local_dir: str = r"D:\Help\automation") -> None:
        """Pull its.json, create a local backup, modify it, and push back to device."""

        # OPTIONAL: keep a remote backup too (uncomment if desired)
        # backup_remote = remote_path + ".bak"
        # self.logger.log(f"[its.json] Creating backup on device: {backup_remote}")
        # shell.run(f"cp {shlex.quote(remote_path)} {shlex.quote(backup_remote)}")

        # 1) Ensure local directory exists
        try:
            os.makedirs(local_dir, exist_ok=True)
        except Exception as e:
            self.logger.log_error(f"[its.json] Failed to ensure local dir: {e}")

        local_path = os.path.join(local_dir, "its.json")

        # 2) Pull file from device → local
        self.logger.log(f"[its.json] Pulling {remote_path} → {local_path}")
        try:
            files.pull(remote_path, local_path)
        except Exception as e:
            self.logger.log_error(f"[its.json] Pull failed: {e}")
            return

        if not os.path.exists(local_path):
            self.logger.log_error(f"[its.json] Pull failed — file not found at {local_path}")
            return

        # 3) Create a timestamped LOCAL backup before any changes
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_local = os.path.join(local_dir, f"its.json.{ts}.bak")
        try:
            shutil.copy2(local_path, backup_local)
            self.logger.log(f"[its.json] Local backup created → {backup_local}")
        except Exception as e:
            self.logger.log_error(f"[its.json] Local backup failed: {e}")
            # Continue anyway; not fatal

        # 4) Load JSON preserving order
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f, object_pairs_hook=OrderedDict)
        except Exception as e:
            self.logger.log_error(f"[its.json] Failed to parse JSON: {e}")
            return

        # 5) Modify 'security' section
        if "security" in data and isinstance(data["security"], (dict, OrderedDict)):
            sec = OrderedDict(data["security"])  # preserve order
            sec["enable"] = "Yes"
            sec["checkCrl"] = "Permissive"
            sec["checkLoadedCertificates"] = False

            # Region-based directories
            dirs = sec.get("directories", OrderedDict())
            if "eu" in dirs:
                dirs["eu"] = "/data/v2xmgr/etc/MBD"
            else:
                # If EU not present, set CN default
                dirs["cn"] = "/data/v2xmgr/etc/test_certs/security_cn"
            sec["directories"] = dirs

            # Insert checkTimestamp right after checkLoadedCertificates
            new_sec = OrderedDict()
            for key, value in sec.items():
                new_sec[key] = value
                if key == "checkLoadedCertificates":
                    new_sec["checkTimestamp"] = False
            data["security"] = new_sec

        # 6) Insert 'logging' after 'security'
        new_data = OrderedDict()
        for key, value in data.items():
            new_data[key] = value
            if key == "security":
                new_data["logging"] = OrderedDict([
                    ("logLevel", "Debug"),
                    ("debugComponents", ["SEC"]),
                ])

        # 7) Modify 'hsm'
        if "hsm" in new_data:
            new_data["hsm"] = {"type": "Emulated"}

        # 8) Disable geofencing
        if "geofencing" in new_data and isinstance(new_data["geofencing"], dict):
            new_data["geofencing"]["enable"] = False

        # 9) Write modified JSON back locally (normalize ["SEC"] formatting)
        json_str = json.dumps(new_data, indent=2, separators=(",", ": "))
        json_str = re.sub(r'\[\s*"SEC"\s*\]', '["SEC"]', json_str)

        
        # 10) Push the modified file back to the device
        try:
            files.push(local_path, remote_path, force=True)
            self.logger.log(f"[its.json] Pushed modified file → {remote_path}")
        except Exception as e:
            self.logger.log_error(f"[its.json] Push failed: {e}")
        finally:
            # Always log the local backup location
            self.logger.log(f"[its.json] Local backup retained at {backup_local}")

            # OPTIONAL: set sane permissions on its.json (adjust to your policy)
            try:
                shell.run(f"chmod 644 {shlex.quote(remote_path)}", timeout=10)
                self.logger.log(f"[its.json] Applied permissions 644 to {remote_path}")
            except Exception as pe:
                self.logger.log_error(f"[its.json] chmod failed: {pe}")

            # OPTIONAL: quick verification check (e.g., file exists and readable)
            try:
                verify = shell.run(f"test -r {shlex.quote(remote_path)} && echo OK || echo FAIL", timeout=10).strip()
                self.logger.log(f"[its.json] Post-push verification: {verify}")
            except Exception as ve:
                self.logger.log_error(f"[its.json] Verification failed: {ve}")

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



    @staticmethod
    def is_icon_sf25(version_output: str) -> bool:
        """Return True if 'iconsf25' is found in the version output (case-insensitive)."""
        if version_output is None:
            return False
        return "iconsf25" in version_output



from typing import List, Tuple, Union

def run_region_test(
    region: str,
    shell: SSHShell,
    files: SSHFileManager,
    logger: Logger,
    log_file: str,
    commands: List[Union[str, Tuple]]
) -> None:
    """
    Run cybersecurity test procedure for a given region over a single SSH session.
    - Logs only (no print()).
    - Uses the same logic as your ADB Helper.
    - Creates a Helper instance bound to the provided logger.
    """

    # Bind Helper to the logger (so all messages go to your log file)
    helper = Helper(logger)
    logger.log(f"\n=== Starting Cybersecurity_{region} Test ===\n")

    # NAD version
    version_output = shell.run("cat /etc/version")

    # Modify its.json (local backup, ordered edits), then prompt for DLT
    time.sleep(5)
    # Helper1.modify_its_json(shell, files)
    helper.ask("Is DLT open")

    # Enable data privacy; optionally start ITS if version indicates iconsf25
    shell.run_batch([("sldd v2xmgr setdataprivacy 1", 15)])
    if Helper.is_icon_sf25(version_output):
        # Keep same behavior as your ADB script (no delay specified there)
        shell.run_batch([("systemctl start its", 5)])

    # Ensure V2X stack is ON (retry logic using unplugged-rt-status-gen)
    helper.is_stack_on(shell)

    # Run rio_inject commands for the selected region
    shell.run_batch(commands, default_delay=10)

    # Prompt and disable data privacy after logs are saved
    helper.ask("Is logs saved?")
    shell.run_batch([("sldd v2xmgr setdataprivacy 0", 1)])

    logger.log(f"\n=== Cybersecurity_{region} Test Completed ===")
    logger.log(f"Logs saved in '{log_file}'\n")


# ================================ main() ====================================
def main():
    # ----------------- Your local paths & remote targets -----------------
    log_file = r"D:\Help\automation\logs\cybersecurity_test.log"
    eu_cert_path = r"D:\Cybersecurity\Snake oil EU\signer_1_EU"
    eu_cn_file_path = r"D:\Cybersecurity\pushfile_data_v2xmgr_etc"
    remote_path = "/data/v2xmgr/etc/"

    # SSH connection settings (hard-coded for simplicity)
    host = "160.48.249.97"    # media_converter
    # host = "169.254.1.97"     # TestBench
    user = "root"
    key_file = r"C:\\Users\\ranjan08.kumar\\.ssh\\nad_root_key_new"
    accept_host_key = True

    # ----------------- Initialize subsystems -----------------
    logger = Logger(log_file=log_file)
    session = SSHSession(host=host, user=user, key_file=key_file, password=None,
                         accept_host_key=accept_host_key, logger=logger)
    session.connect()

    shell = SSHShell(session=session, logger=logger)
    files = SSHFileManager(session=session, logger=logger)
    
    helper = Helper(logger)

    try:
        logger.log("\n=== Initial Setup ===")

        # Push necessary files
        files.push_folder(eu_cn_file_path, remote_path)
        if Helper.is_region_eu(files):
            shell.run("mkdir -p /data/v2xmgr/etc/MBD")
            files.push_folder(eu_cert_path, "/data/v2xmgr/etc/MBD/")

            # Set permissions
            shell.run("chmod 777 /data/v2xmgr/etc/MBD/*")
        shell.run("mv /data/v2xmgr/etc/rio_inject.txt /data/v2xmgr/etc/rio_inject")
        shell.run("chmod 777 /data/v2xmgr/etc/rio_inject /data/v2xmgr/etc/*.bin")

        # Verify all files
        shell.run("ls -l /data/v2xmgr/etc/")

        # Command sets
        commands_EU = [
            "/data/v2xmgr/etc/rio_inject 1 127.0.0.1 /data/v2xmgr/etc/invalid_signature_cam.bin",
            "/data/v2xmgr/etc/rio_inject 1 127.0.0.1 /data/v2xmgr/etc/valid_cam.bin",
            "/data/v2xmgr/etc/rio_inject 1 127.0.0.1 /data/v2xmgr/etc/valid_cam.bin",
        ]
        commands_CN = [
            "/data/v2xmgr/etc/rio_inject 4 127.0.0.1 /data/v2xmgr/etc/invalid_signature_cn_bsm.bin",
            "/data/v2xmgr/etc/rio_inject 4 127.0.0.1 /data/v2xmgr/etc/valid_cn_bsm.bin",
            "/data/v2xmgr/etc/rio_inject 4 127.0.0.1 /data/v2xmgr/etc/valid_cn_bsm.bin",
        ]

        # Determine initial region and run tests
        region_eu = Helper.is_region_eu(files)  # returns True/False/None
        if region_eu is True:
            run_region_test("EU", shell, files, logger, log_file, commands_EU)
            Helper.ask("Is device rebooted and region changed to CN?")
            region_eu = Helper.is_region_eu(files)
            if region_eu is False:
                run_region_test("CN", shell, files, logger, log_file, commands_CN)
        elif region_eu is False:
            run_region_test("CN", shell, files, logger, log_file, commands_CN)
            Helper.ask("Is device rebooted and region changed to EU?")
            region_eu = Helper.is_region_eu(files)
            if region_eu is True:
                run_region_test("EU", shell, files, logger, log_file, commands_EU)
        else:
            logger.log("Region undetermined—defaulting to EU test first.")
            run_region_test("EU", shell, files, logger, log_file, commands_EU)

    except Exception as e:
        logger.log_error(str(e))

    finally:
        session.close()
        logger.log("\n=== Test Session Closed ===\n")


if __name__ == "__main__":
    main()

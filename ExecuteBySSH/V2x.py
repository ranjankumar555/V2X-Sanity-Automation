
#!/usr/bin/env python3
r"""
Convert ADB-based batch to an SSH single-session Python script.

This script provides minimal equivalents of ADBShell, ADBLogger, and Helper,
implemented over a single persistent SSH connection using Paramiko.

Run (PowerShell):
  python .\adb_to_ssh_diag.py

Requirements:
  pip install paramiko
"""

import sys
import time
import shlex
from datetime import datetime
from typing import List, Tuple, Union

try:
    import paramiko
except ImportError:
    print("ERROR: Paramiko required. Install with: pip install paramiko", file=sys.stderr)
    sys.exit(1)

# ----------------------------- Logger -----------------------------
class ADBLogger:
    def __init__(self, log_file: str):
        self.log_file = log_file
        # Touch the file
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{ts}] Log started\n")
        except Exception as e:
            print(f"WARN: Unable to initialize log file {self.log_file}: {e}")

    def log(self, msg: str):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{ts}] {msg}"
        print(line)
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(line + "\n")
        except Exception:
            pass

# ----------------------------- SSH helpers -----------------------------
def _drain_channel(chan: paramiko.Channel, idle_window: float = 0.20) -> str:
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

# ----------------------------- Shell -----------------------------
class ADBShell:
    """
    SSH-backed shell that mimics the minimal ADBShell API used by the user code:
      - run(cmd)
      - run_batch(commands, default_delay=2)
      - close()
    """
    def __init__(self, host: str, user: str, key_file: str, logger: ADBLogger,
                 accept_host_key: bool = True):
        self.host = host
        self.user = user
        self.key_file = key_file
        self.logger = logger
        self.accept_host_key = accept_host_key
        self.client = None
        self.chan = None
        self._connect()

    def _connect(self):
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
            allow_agent=True,
            look_for_keys=True,
            timeout=20,
        )
        self.logger.log("SSH connected.")
        # Open single interactive bash login shell
        self.chan = self.client.invoke_shell(width=200, height=50)
        self.chan.send("bash -li\n")
        time.sleep(0.8)
        _drain_channel(self.chan, idle_window=0.25)

    def run(self, command: str, timeout: int = 60) -> str:
        """Run a command inside the persistent shell and return stdout."""
        quoted = shlex.quote(command)
        marked = f"bash -lc {quoted}; echo __RC__$?\n"
        self.logger.log(f"SHELL: {command}")
        self.chan.send(marked)

        start = time.time()
        output = ''
        rc = None
        while True:
            chunk = _drain_channel(self.chan, idle_window=0.20)
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
        Run a list of commands. Each item may be:
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

    def close(self):
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
        self.logger.log("SSH connection closed.")

# ----------------------------- Helper -----------------------------
class Helper:
    @staticmethod
    def ask(prompt: str):
        print(f"[QUESTION] {prompt} (Press Enter to continue)")
        try:
            input()
        except EOFError:
            # Non-interactive environment
            pass

    @staticmethod
    def is_icon_sf25(version_output: str) -> bool:
        # Simple heuristic: look for 'SF25' or 'sf25' in the version string
        return 'SF25' in version_output or 'sf25' in version_output

    @staticmethod
    def is_stack_on(shell: ADBShell) -> bool:
        status = shell.run('systemctl is-active its', timeout=20).strip().lower()
        if status == 'active':
            shell.logger.log('ITS service is active.')
            return True
        else:
            shell.logger.log(f'ITS service state: {status}. Attempting to start...')
            shell.run('systemctl start its', timeout=30)
            time.sleep(2)
            status2 = shell.run('systemctl is-active its', timeout=20).strip().lower()
            shell.logger.log(f'ITS service state after start attempt: {status2}')
            return status2 == 'active'

# ----------------------------- Main -----------------------------
def main():
    # Use a consistent log file
    log_file = r"D:\Help\automation\logs\v2x_test.log"

    # Assign SSH connection details here (no CLI args needed)
    host = "160.48.249.97"
    user = "root"
    key_file = r"C:\Users\ranjan08.kumar\.ssh\nad_root_key_new"
    accept_host_key = True

    # Initialize logger and single-session shell
    logger = ADBLogger(log_file=log_file)
    shell = ADBShell(host=host, user=user, key_file=key_file, logger=logger, accept_host_key=accept_host_key)

    try:
        version_output = shell.run("cat /etc/version")
        # logger.log(f"NAD version:\n{version_output}")

        Helper.ask("Is DLT open")
        shell.run_batch([("sldd v2xmgr setdataprivacy 1", 8)])
        if Helper.is_icon_sf25(version_output):
            shell.run_batch([("systemctl start its", 5)])

        Helper.is_stack_on(shell)

        commands = [
            "sldd power requestset 2004 7",
            "sldd power requestset 2004 2",
            "sldd power requestset 2004 5",
            "pgrep -f its",
            "ps -fC its",
            "ps -fC its",
            ("killall its", 30),  # custom delay
            "sldd power requestset 2002 1",
        ]

        shell.run_batch(commands, default_delay=2)

    finally:
        Helper.ask("Is logs saved")
        shell.run_batch([("sldd v2xmgr setdataprivacy 0", 3)])
        logger.log(f"V2x Testcase Completed. Logs are saved in '{log_file}'.")
        shell.close()

if __name__ == "__main__":
    main()


import os
import os
import sys
import time
import socket
import shlex
import posixpath
from typing import List, Tuple, Union, Optional

from framework.adbshell import ADBLogger
try:
    import paramiko
except ImportError:
    print("ERROR: This script requires the 'paramiko' package. Install it with: pip install paramiko", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------
def is_ssh_port_open(host: str, port: int = 22, timeout: float = 3.0) -> bool:
    """Return True if the given host is reachable on SSH port 22."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def select_available_host(hosts: List[str], logger: Optional[ADBLogger] = None) -> Optional[str]:
    """Pick the first reachable host from the given list."""
    for host in hosts:
        if is_ssh_port_open(host):
            if logger:
                logger.log(f"Using available host: {host}")
            return host
        if logger:
            logger.log(f"Host not reachable: {host}")
    return None

# ============================= SSH Session =================================
class SSHSession:
    """
    Owns the Paramiko SSHClient and provides:
      - a single interactive bash shell channel
      - an SFTP client for file transfers
    """
    def __init__(self, host: str, user: str, key_file: Optional[str], logger: ADBLogger,
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
    def __init__(self, session: SSHSession, logger: ADBLogger):
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
            self.logger.log(out)
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

    def close(self):
        """Close the SSH session cleanly."""
        if self.session:
            self.session.close()


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
    def __init__(self, session: SSHSession, logger: ADBLogger):
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

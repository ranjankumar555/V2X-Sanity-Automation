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
import uuid
import re
from collections import OrderedDict

# =====================================================
# Colors for Console Output
# =====================================================
class Colors:
    """ANSI color codes for console output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

 # =====================================================
# Logger
# =====================================================
class ADBLogger:
    """
    Logger that writes to file only by default.
    Provides separate colored console output methods for optional display.
    """
    
    def __init__(self, log_file=None):
        self.log_file = log_file

        if self.log_file:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def log(self, message, msg_type='info'):
        """Write message to file only (silent).
        
        Args:
            message: The message to log
            msg_type: Type of message - 'info', 'success', 'warning', 'error' (default: 'info')
        """
        if message is None:
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add prefix based on message type
        prefix_map = {
            'error': 'ERROR: ',
            'success': 'SUCCESS: ',
            'warning': 'WARNING: ',
            'info': ''
        }
        prefix = prefix_map.get(msg_type, '')
        
        line = f"[{timestamp}] {prefix}{message}"
        
        # Write to file only (no console output)
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def print_red(self, message):
        """Print message in red color to console AND log to file"""
        if message is None:
            return
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] ERROR: {message}"
        
        print(f"{Colors.RED}{line}{Colors.RESET}")
        
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def print_green(self, message):
        """Print message in green color to console AND log to file"""
        if message is None:
            return
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        
        print(f"{Colors.GREEN}{line}{Colors.RESET}")
        
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def print_yellow(self, message):
        """Print message in yellow color to console AND log to file"""
        if message is None:
            return
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] WARNING: {message}"
        
        print(f"{Colors.YELLOW}{line}{Colors.RESET}")
        
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def print_blue(self, message):
        """Print message in blue color to console AND log to file"""
        if message is None:
            return
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        
        print(f"{Colors.BLUE}{line}{Colors.RESET}")
        
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def print_default(self, message):
        """Print message in default color to console AND log to file (no ANSI codes)"""
        if message is None:
            return
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        
        print(line)  # No color codes
        
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def log_error(self, message):
        """Write error message to file only (silent).
        
        Args:
            message: The error message to log
        """
        if message is None:
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] ERROR: {message}"
        
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

# =====================================================
# JSON Utilities - Handle malformed JSON with trailing commas
# =====================================================
def load_json_with_fallback(file_path, logger=None, use_ordered_dict=True):
    """
    Load JSON from file, handling trailing commas and malformed JSON.
    
    Args:
        file_path: Path to JSON file
        logger: Optional logger instance
        use_ordered_dict: Whether to preserve key order
    
    Returns:
        Loaded JSON data as dict or OrderedDict
    
    Strategy:
        1. Try standard json.load() first
        2. If that fails, try JSONDecoder.raw_decode() to parse first valid JSON object
        3. If that fails, try cleaning trailing commas and retry
    """
    if not os.path.exists(file_path):
        if logger:
            logger.log_error(f"File not found: {file_path}")
        return None
    
    hook = OrderedDict if use_ordered_dict else None
    
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Attempt 1: Standard JSON parsing
    try:
        return json.loads(text, object_pairs_hook=hook)
    except json.JSONDecodeError as e:
        if logger:
            logger.log(f"[INFO] Standard JSON parsing failed: {e}. Attempting fallback...")
    
    # Attempt 2: Parse first valid JSON object (ignores trailing commas/data)
    try:
        decoder = json.JSONDecoder(object_pairs_hook=hook)
        obj, _ = decoder.raw_decode(text.lstrip())
        if logger:
            logger.log("[INFO] Successfully parsed JSON using raw_decode (first object)")
        return obj
    except json.JSONDecodeError as e:
        if logger:
            logger.log(f"[INFO] raw_decode also failed: {e}. Attempting cleanup...")
    
    # Attempt 3: Clean trailing commas before closing braces/brackets
    try:
        # Remove trailing commas before closing brackets/braces
        cleaned_text = re.sub(r',\s*([\]\}])', r'\1', text)
        result = json.loads(cleaned_text, object_pairs_hook=hook)
        if logger:
            logger.log("[INFO] Successfully parsed JSON after removing trailing commas")
        return result
    except json.JSONDecodeError as e:
        if logger:
            logger.log_error(f"Failed to parse JSON from {file_path}: {e}")
        return None

# ------------------------------
# Shell (persistent session)
# ------------------------------
class ADBShell:
    def __init__(self, adb_cmd="adb", logger=None, reconnect_attempts=3, reconnect_delay=5):
        self.adb_cmd = adb_cmd
        self.logger = logger or ADBLogger()
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay

        self.proc = None
        self.q = queue.Queue()

        self._start_shell()

    # -------------------------------------------------
    def _start_shell(self):
        """Start persistent shell and reader thread."""
        self.logger.log("=== Starting ADB Shell ===")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.log(f"[{ts}]")

        subprocess.run(
            [self.adb_cmd, "wait-for-device", "root"],
            check=True
        )
        time.sleep(1)

        self.proc = subprocess.Popen(
            [self.adb_cmd, "shell"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        self.reader_thread = threading.Thread(
            target=self._enqueue_output,
            daemon=True
        )
        self.reader_thread.start()

    # -------------------------------------------------
    def _enqueue_output(self):
        """Continuously enqueue stdout lines."""
        for line in self.proc.stdout:
            self.q.put(line)

    # -------------------------------------------------
    def _reconnect_if_needed(self):
        """Reconnect shell if process died."""
        if self.proc and self.proc.poll() is None:
            return

        self.logger.log_error("Shell lost. Attempting to reconnect...")
        for attempt in range(1, self.reconnect_attempts + 1):
            try:
                self._start_shell()
                self.logger.log(f"Reconnected shell (attempt {attempt})")
                return
            except Exception as e:
                self.logger.log_error(f"Reconnect attempt {attempt} failed: {e}")
                time.sleep(self.reconnect_delay)

        raise RuntimeError("Could not reconnect to ADB shell")

    # -------------------------------------------------
    def _clean_sentinel_from_output(self, line: str) -> str:
        """
        Remove sentinel echo command from output line.
        Removes everything from "; echo __CMD_DONE_" onwards including the marker.
        
        Examples:
            Input:  "sh-3.2# chmod 777 /data/v2xmgr/etc/ ; echo __CMD_DONE_xyz__"
            Output: "sh-3.2# chmod 777 /data/v2xmgr/etc/"
            
            Input:  "__CMD_DONE_xyz__"
            Output: "" (empty - line is just the marker)
            
        Args:
            line: Line potentially containing sentinel echo command
            
        Returns:
            str: Cleaned line without sentinel echo command, or empty string if line is only marker
        """
        # Remove everything from "; echo __CMD_DONE_" onwards
        if "; echo __CMD_DONE_" in line:
            cleaned = line.split("; echo __CMD_DONE_")[0].strip()
            return cleaned
        
        # Also handle partial markers that may span lines (e.g., "__CMD_DONE_xyz__")
        if line.strip().startswith("__CMD_DONE_") or line.strip().endswith("__"):
            # This line is just part of the sentinel marker, skip it
            return ""
        
        return line.strip()
    
    # -------------------------------------------------
    def run(self, command, timeout=10, use_sentinel=True):
        """
        Persistent ADB shell runner with optional ultra-fast sentinel mode.
        
        Features:
        - Logs command being executed
        - Logs each line of output in real-time
        - Filters sentinel completion marker from output
        - use_sentinel=True: Fastest execution with explicit completion marker
        
        Args:
            command: Command to execute
            timeout: Response timeout in seconds (default: 10)
            use_sentinel: Use sentinel mode for ultra-fast completion detection (default: True)
            
        Returns:
            str: Command output (without sentinel marker)
        """
        self._reconnect_if_needed()

        # Log the command being executed
        # self.logger.print_default(f"sh-3.2# {command}")

        output_lines = []
        start_time = time.time()
        shell_prompt_pattern = re.compile(r".*[#\$]\s*$")

        sentinel = None
        if use_sentinel:
            sentinel = f"__CMD_DONE_{uuid.uuid4().hex}__"
            full_command = f"{command} ; echo {sentinel}"
        else:
            full_command = command

        # Send command
        if self.proc.stdin:
            self.proc.stdin.write(full_command + "\n")
            self.proc.stdin.flush()

        while True:
            # Hard safety timeout only
            if time.time() - start_time > timeout:
                break

            try:
                line = self.q.get_nowait()
            except queue.Empty:
                continue  # zero-delay polling

            line = line.rstrip("\r\n")

            # --- Sentinel-based ultra-fast exit ---
            if use_sentinel and sentinel in line:
                while True:
                    try:
                        extra = self.q.get_nowait().rstrip("\r\n")
                        # Clean and filter sentinel markers from remaining output
                        cleaned_extra = self._clean_sentinel_from_output(extra)
                        if cleaned_extra:
                            self.logger.print_default(cleaned_extra)
                            output_lines.append(cleaned_extra)
                    except queue.Empty:
                        break
                break

            # --- Prompt-based fallback ---
            if not use_sentinel and shell_prompt_pattern.match(line.strip()):
                # Shell prompt detected - drain remaining output
                while True:
                    try:
                        extra = self.q.get_nowait().rstrip("\r\n")
                        if extra.strip():
                            self.logger.print_default(extra)
                            output_lines.append(extra)
                    except queue.Empty:
                        break
                break

            # Log and append actual output (filter sentinel)
            if line.strip():
                # Clean sentinel from all output lines
                cleaned_line = self._clean_sentinel_from_output(line)
                # Only append and log if there's actual content after cleaning
                if cleaned_line:
                    self.logger.print_default(cleaned_line)
                    output_lines.append(cleaned_line)

        return "\n".join(output_lines)

    # -------------------------------------------------
    def run_batch(self, commands, default_delay=0):
        for item in commands:
            if isinstance(item, tuple):
                cmd, delay = item
            else:
                cmd, delay = item, default_delay

            self.run(cmd)
            if delay:
                time.sleep(delay)

    # -------------------------------------------------
    def close(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write("exit\n")
                self.proc.stdin.flush()
                self.proc.terminate()
            except Exception:
                pass

        self.logger.log("=== ADB Shell Closed ===")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.log(f"[{ts}]")

# ------------------------------
# File Manager
# ------------------------------
import os
import subprocess

class ADBFileManager:
    def __init__(self, adb_cmd="adb", logger=None):
        self.adb_cmd = adb_cmd
        self.logger = logger or ADBLogger()

    def push(self, local_path, remote_path, force=False):
        """
        Push file or folder to device.
        """
        try:
            subprocess.run(
                [self.adb_cmd, "push", local_path, remote_path],
                check=True,
                text=True
            )
            self.logger.log(f"[OK] Pushed {local_path} → {remote_path}")

        except subprocess.CalledProcessError as e:
            self.logger.log_error(f"Failed to push {local_path}: {e}")

    def pull(self, remote_path, local_path):
        """
        Pull file or folder from device.
        """
        try:
            subprocess.run(
                [self.adb_cmd, "pull", remote_path, local_path],
                check=True,
                text=True
            )
            self.logger.log(f"[OK] Pulled {remote_path} → {local_path}")

        except subprocess.CalledProcessError as e:
            self.logger.log_error(f"Failed to pull {remote_path}: {e}")

    def push_folder(self, local_folder, remote_folder):
        """
        Push entire folder to device.
        """
        if not os.path.isdir(local_folder):
            self.logger.log_error(f"{local_folder} is not a directory")
            return

        try:
            subprocess.run(
                [self.adb_cmd, "wait-for-device"],
                check=True
            )

            subprocess.run(
                [self.adb_cmd, "push", local_folder, remote_folder],
                check=True
            )

            self.logger.log(f"[OK] Pushed {local_folder} → {remote_folder}")

        except subprocess.CalledProcessError as e:
            self.logger.log_error(f"ADB push folder failed: {e}")
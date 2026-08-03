"""
Base Test Framework for V2X Automation

Provides a unified testing framework that automatically handles Master vs SOP Version mode.
- Master: Runs sldd directly
- SOP: Sets up /log/sldd, applies permissions, and runs from there

Usage:
    class MyTest(TestBase):
        def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
            return [
                "sldd v2xmgr setdataprivacy 1",
                ("sldd power requestset 2004 7", 3),
            ]
        
        def setup_custom(self):
            # Optional: test-specific setup
            pass
        
        def teardown_custom(self):
            # Optional: test-specific cleanup
            pass
    
    test = MyTest(test_name="v2x_test", log_file="logs/v2x.log")
    test.run()
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Union, Tuple, Optional, Dict, Any
from abc import ABC, abstractmethod

# Add parent directory to path to import adbshell
PARENT_DIR = Path(__file__).parent.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from framework.adbshell import ADBShell, ADBLogger, ADBFileManager
from framework.helper import Helper
from framework.sshShell import SSHSession, SSHShell, SSHFileManager, select_available_host

class TestConfig:
    """Configuration for a single test case."""
    
    def __init__(
        self,
        test_name: str,
        log_file: str,
        adb_cmd: str = "adb1",
        sop_setup_files: Optional[Dict[str, str]] = None,
        ssh_host: Optional[Union[str, List[str]]] = None,
        ssh_user: str = "root",
        ssh_key_file: Optional[str] = None,
        ssh_password: Optional[str] = None,
        ssh_port: int = 22,
        accept_host_key: bool = True
    ):
        """
        Initialize test configuration.
        
        Args:
            test_name: Name of the test (e.g., "v2x", "dtc")
            log_file: Path to log file
            adb_cmd: ADB command (default: "adb1")
            sop_setup_files: Dict mapping local paths to remote paths for SOP mode
                            e.g., {"local/sldd": "/log/sldd"}
            ssh_host: SSH host or list of hosts for SSH-based tests
            ssh_user: SSH username
            ssh_key_file: Optional SSH private key file
            ssh_password: Optional SSH password
            ssh_port: SSH port number
            accept_host_key: Accept unknown host keys if True
        """
        self.test_name = test_name
        self.log_file = log_file
        self.adb_cmd = adb_cmd
        self.sop_setup_files = sop_setup_files or {}
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_key_file = ssh_key_file
        self.ssh_password = ssh_password
        self.ssh_port = ssh_port
        self.accept_host_key = accept_host_key
        self.version_output = None
        self.is_sop_mode = False


class TestBase(ABC):
    """
    Base class for unified V2X automation tests.
    
    Automatically handles Master vs SOP modes without duplicating code.
    """
    
    def __init__(
        self,
        test_name: str,
        log_file: str,
        adb_cmd: str = "adb1",
        sop_setup_files: Optional[Dict[str, str]] = None,
        require_sop_setup: bool = False,
        use_adb: bool = True
    ):
        """
        Initialize base test.
        
        Args:
            test_name: Name of the test
            log_file: Path to log file
            adb_cmd: ADB command
            sop_setup_files: Files to push for SOP mode
            require_sop_setup: If True, mandatory SOP setup is skipped if not in SOP mode
            use_adb: If False, do not initialize ADB shell/file manager (used by SSHTestBase)
        """
        self.config = TestConfig(test_name, log_file, adb_cmd, sop_setup_files)
        self.require_sop_setup = require_sop_setup
        
        # Initialize logger and shell/file manager
        os.makedirs(os.path.dirname(self.config.log_file) or ".", exist_ok=True)
        self.logger = ADBLogger(log_file=self.config.log_file)
        if use_adb:
            self.shell = ADBShell(adb_cmd=self.config.adb_cmd, logger=self.logger)
            self.files = ADBFileManager(adb_cmd=self.config.adb_cmd, logger=self.logger)
        else:
            self.shell = None
            self.files = None

        self.logger.log(f"\n{'='*60}")
        self.logger.log(f"Test: {test_name}")
        self.logger.log(f"Log File: {self.config.log_file}")
        self.logger.log(f"{'='*60}\n")
    
    @abstractmethod
    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
        """
        Get the list of commands to execute.
        
        Returns:
            List of commands. Each can be:
            - str: Command to run
            - Tuple[str, int]: (command, delay_seconds)
        
        Example:
            return [
                "sldd v2xmgr setdataprivacy 1",
                ("sldd power requestset 2004 7", 3),
                "sldd v2xmgr setdataprivacy 0",
            ]
        """
        pass
    
    def setup_custom(self) -> None:
        """Override for test-specific setup logic."""
        pass
    
    def teardown_custom(self) -> None:
        """Override for test-specific cleanup logic."""
        pass
    
    def _wrap_command(self, cmd: str) -> str:
        """
        Wrap command to use sldd or /log/sldd based on mode.
        
        Args:
            cmd: Command string that may contain 'sldd'
        
        Returns:
            Command with appropriate path (sldd or /log/sldd)
        """
        if self.config.is_sop_mode:
            # Replace 'sldd' with '/log/sldd' if not already prefixed
            if not cmd.startswith('/log/'):
                cmd = cmd.replace('sldd ', '/log/sldd ', 1)
        return cmd
    
    def _setup_sop_mode(self) -> None:
        """Setup SOP mode prerequisites if needed."""
        if self.config.is_sop_mode:
            self.logger.log("Preparing SOP mode...")
            
            # Push files if provided
            for local_path, remote_path in self.config.sop_setup_files.items():
                if os.path.exists(local_path):
                    self.logger.log(f"Pushing {local_path} to {remote_path}")
                    self.files.push(local_path, remote_path)
                    time.sleep(0.5)
            
            # Mount with exec permission
            self.logger.log("Remounting /log/ with exec permission...")
            self.shell.run("mount -o remount,exec /log/")
            time.sleep(1)
            
            # Set permissions on binaries
            self.logger.log("Setting permissions on /log/sldd and /log/sldd_v2xmgr...")
            self.shell.run("chmod 777 /log/sldd /log/sldd_v2xmgr")
            time.sleep(0.5)
    
    def _teardown_sop_mode(self) -> None:
        """Cleanup SOP mode if needed (optional)."""
        pass
    
    def _determine_mode(self) -> None:
        """Determine if running in Master or SOP mode."""
        self.config.version_output = self.shell.run("cat /etc/version")
        self.logger.print_blue(f"cat /etc/version \n{self.config.version_output}")
        if Helper.is_binary_sop(self.config.version_output):
            self.config.is_sop_mode = True
            self.logger.log("Mode: SOP (binary running from /log/)")
        else:
            # is_sop_fallback = False
            
            # if not self.config.version_output or len(self.config.version_output.strip()) < 3:
            #     self.logger.log("[INFO] Version file empty; attempting runtime detection...")
            #     diag = Helper.detect_device_type(self.shell, self.logger)
                
            #     if diag.get("is_sop") is True:
            #         is_sop_fallback = True
            #         self.logger.log("[INFO] Fallback detection: SOP mode confirmed")
            
            # if is_sop_fallback:
            #     self.config.is_sop_mode = True
            #     self.logger.log("Mode: SOP (binary running from /log/)")
            # else:
            self.config.is_sop_mode = False
            self.logger.log("Mode: MASTER (native binary)")
    
    def run(self) -> bool:
        """
        Execute the complete test flow.
        
        Supports two lifecycle patterns:
        1. Traditional: setup_custom() -> get_commands() -> teardown_custom()
        2. Advanced: setup_custom() -> execute_custom() -> teardown_custom() -> get_verification_custom()
        
        Returns:
            True if test completed successfully, False otherwise
        """
        try:
            # Determine mode
            self._determine_mode()
            
            # Setup SOP if needed
            self._setup_sop_mode()
            
            # Custom setup
            self.setup_custom()
            
            # Execute test commands - support two patterns
            has_execute_custom = hasattr(self, 'execute_custom') and callable(getattr(self, 'execute_custom'))
            
            if has_execute_custom:
                # Pattern B: Use execute_custom() for direct test execution
                self.logger.log("\n[INFO] Using execute_custom() pattern for test execution\n")
                self.execute_custom()
            else:
                # Pattern A: Traditional get_commands() pattern
                commands = self.get_commands()
                
                # Wrap all commands based on mode
                wrapped_commands = []
                for cmd in commands:
                    if isinstance(cmd, tuple):
                        cmd_str, delay = cmd
                        wrapped_cmd = self._wrap_command(cmd_str)
                        wrapped_commands.append((wrapped_cmd, delay))
                    else:
                        wrapped_cmd = self._wrap_command(cmd)
                        wrapped_commands.append(wrapped_cmd)
                
                # Run commands
                if wrapped_commands:
                    self.shell.run_batch(wrapped_commands, default_delay=2)
            
            # Custom teardown
            self.teardown_custom()
            
            # Post-test verification - if method exists, call it
            has_verification_custom = hasattr(self, 'get_verification_custom') and callable(getattr(self, 'get_verification_custom'))
            
            if has_verification_custom:
                self.logger.log("\n[INFO] Running post-test verification (get_verification_custom)\n")
                self.get_verification_custom()
            
            # SOP cleanup
            self._teardown_sop_mode()
            
            self.logger.log(f"\n{'='*60}")
            self.logger.log(f"[OK] Test '{self.config.test_name}' COMPLETED SUCCESSFULLY")
            self.logger.log(f"Logs saved in '{self.config.log_file}'")
            self.logger.log(f"{'='*60}\n")
            
            return True
            
        except Exception as e:
            self.logger.log_error(f"Test failed with error: {str(e)}")
            return False
        
        finally:
            self.shell.close()
    
    def __del__(self):
        """Ensure shell is closed."""
        try:
            if hasattr(self, 'shell') and self.shell is not None:
                self.shell.close()
        except:
            pass


class CompositeShell:
    """Run commands on primary and secondary shells if both are available."""

    def __init__(self, primary, secondary=None):
        self.primary = primary
        self.secondary = secondary

    def run(self, command, timeout=60, **kwargs):
        output = self.primary.run(command, timeout=timeout, **kwargs)
        if self.secondary is not None:
            try:
                self.secondary.run(command, timeout=timeout, **kwargs)
            except Exception as e:
                if hasattr(self.primary, 'logger'):
                    self.primary.logger.log_error(f"Secondary shell command failed: {e}")
        return output

    def run_batch(self, commands, default_delay=2, default_timeout=60):
        self.primary.run_batch(commands, default_delay=default_delay, default_timeout=default_timeout)
        if self.secondary is not None:
            try:
                self.secondary.run_batch(commands, default_delay=default_delay, default_timeout=default_timeout)
            except Exception as e:
                if hasattr(self.primary, 'logger'):
                    self.primary.logger.log_error(f"Secondary shell batch failed: {e}")

    def close(self):
        try:
            self.primary.close()
        except Exception:
            pass
        if self.secondary is not None:
            try:
                self.secondary.close()
            except Exception:
                pass


class CompositeFileManager:
    """Push/pull through primary and secondary file managers if both are available."""

    def __init__(self, primary, secondary=None):
        self.primary = primary
        self.secondary = secondary

    def push(self, local_path, remote_path, force=True):
        result = self.primary.push(local_path, remote_path, force=force)
        if self.secondary is not None:
            try:
                self.secondary.push(local_path, remote_path, force=force)
            except Exception as e:
                if hasattr(self.primary, 'logger'):
                    self.primary.logger.log_error(f"Secondary file push failed: {e}")
        return result

    def pull(self, remote_path, local_path):
        result = self.primary.pull(remote_path, local_path)
        if self.secondary is not None:
            try:
                self.secondary.pull(remote_path, local_path)
            except Exception as e:
                if hasattr(self.primary, 'logger'):
                    self.primary.logger.log_error(f"Secondary file pull failed: {e}")
        return result

    def push_folder(self, local_dir, remote_dir):
        result = self.primary.push_folder(local_dir, remote_dir)
        if self.secondary is not None:
            try:
                self.secondary.push_folder(local_dir, remote_dir)
            except Exception as e:
                if hasattr(self.primary, 'logger'):
                    self.primary.logger.log_error(f"Secondary push_folder failed: {e}")
        return result

    def read_text(self, remote_path):
        return self.primary.read_text(remote_path)

    def write_text(self, remote_path, text, encoding='utf-8'):
        result = self.primary.write_text(remote_path, text, encoding=encoding)
        if self.secondary is not None:
            try:
                self.secondary.write_text(remote_path, text, encoding=encoding)
            except Exception as e:
                if hasattr(self.primary, 'logger'):
                    self.primary.logger.log_error(f"Secondary write_text failed: {e}")
        return result

    def chmod(self, remote_path, mode):
        result = self.primary.chmod(remote_path, mode)
        if self.secondary is not None:
            try:
                self.secondary.chmod(remote_path, mode)
            except Exception as e:
                if hasattr(self.primary, 'logger'):
                    self.primary.logger.log_error(f"Secondary chmod failed: {e}")
        return result

    def exists(self, remote_path):
        return self.primary.exists(remote_path)

    def list_dir(self, remote_dir):
        return self.primary.list_dir(remote_dir)


class SSHTestBase(TestBase):
    """Base class for SSH-backed tests using Paramiko-based SSHSession.

    Supports SSH-only, ADB-only, or both transports if available.
    """

    def __init__(
        self,
        test_name: str,
        log_file: str,
        ssh_host: Optional[Union[str, List[str]]] = None,
        ssh_user: str = "root",
        ssh_key_file: Optional[str] = None,
        ssh_password: Optional[str] = None,
        ssh_port: int = 22,
        accept_host_key: bool = True,
        adb_cmd: str = "adb1",
        sop_setup_files: Optional[Dict[str, str]] = None,
        require_sop_setup: bool = False,
        use_adb: bool = True,
        host_selection_timeout: float = 3.0,
    ):
        super().__init__(
            test_name=test_name,
            log_file=log_file,
            adb_cmd=adb_cmd,
            sop_setup_files=sop_setup_files,
            require_sop_setup=require_sop_setup,
            use_adb=use_adb,
        )

        self.config.ssh_host = ssh_host
        self.config.ssh_user = ssh_user
        self.config.ssh_key_file = ssh_key_file
        self.config.ssh_password = ssh_password
        self.config.ssh_port = ssh_port
        self.config.accept_host_key = accept_host_key

        env_hosts = self._resolve_env_ssh_hosts()
        if env_hosts and self.config.ssh_host is None:
            self.config.ssh_host = env_hosts

        self.adb_shell = None
        self.adb_files = None
        self.ssh_session = None
        self.ssh_shell = None
        self.ssh_files = None

        self._initialize_transports(adb_cmd=adb_cmd, host_selection_timeout=host_selection_timeout)

        if self.ssh_shell and self.adb_shell:
            self.shell = CompositeShell(self.ssh_shell, self.adb_shell)
            self.files = CompositeFileManager(self.ssh_files, self.adb_files)
        elif self.ssh_shell:
            self.shell = self.ssh_shell
            self.files = self.ssh_files
        elif self.adb_shell:
            self.shell = self.adb_shell
            self.files = self.adb_files
        else:
            raise RuntimeError("No available transport found: both SSH and ADB initialization failed")

    def _resolve_env_ssh_hosts(self) -> Optional[List[str]]:
        hosts = os.getenv("SSH_HOSTS") or os.getenv("SSH_HOST")
        if not hosts:
            return None
        if isinstance(hosts, str):
            if "," in hosts or ";" in hosts:
                normalized = hosts.replace(";", ",")
                return [h.strip() for h in normalized.split(",") if h.strip()]
            return [hosts.strip()]
        return None

    def _initialize_transports(self, adb_cmd: str, host_selection_timeout: float):
        ssh_available = False
        adb_available = False

        if self.config.ssh_host:
            try:
                self.ssh_session = self._create_ssh_session()
                self.ssh_session.connect()
                self.ssh_shell = SSHShell(self.ssh_session, self.logger)
                self.ssh_files = SSHFileManager(self.ssh_session, self.logger)
                ssh_available = True
                self.logger.log(f"SSH transport initialized for host {self.config.ssh_host}")
            except Exception as e:
                self.logger.log_error(f"SSH transport unavailable: {e}")
                self.ssh_session = None
                self.ssh_shell = None
                self.ssh_files = None
        else:
            self.logger.log("No SSH host configured; skipping SSH transport initialization")

        try:
            self.adb_shell = ADBShell(adb_cmd=self.config.adb_cmd, logger=self.logger)
            self.adb_files = ADBFileManager(adb_cmd=self.config.adb_cmd, logger=self.logger)
            adb_available = True
            self.logger.log("ADB transport initialized")
        except Exception as e:
            self.logger.log_error(f"ADB transport unavailable: {e}")
            self.adb_shell = None
            self.adb_files = None

        if not ssh_available and not adb_available:
            raise RuntimeError("No transport is available: SSH and ADB both failed")

    def _create_ssh_session(self) -> SSHSession:
        if isinstance(self.config.ssh_host, list):
            selected = select_available_host(self.config.ssh_host, logger=self.logger)
            if selected is None:
                raise RuntimeError(f"No available SSH host found in list: {self.config.ssh_host}")
            self.config.ssh_host = selected
        elif self.config.ssh_host is None:
            raise RuntimeError("SSH host is not configured")

        return SSHSession(
            host=self.config.ssh_host,
            user=self.config.ssh_user,
            key_file=self.config.ssh_key_file,
            logger=self.logger,
            password=self.config.ssh_password,
            accept_host_key=self.config.accept_host_key,
        )

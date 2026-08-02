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

class TestConfig:
    """Configuration for a single test case."""
    
    def __init__(
        self,
        test_name: str,
        log_file: str,
        adb_cmd: str = "adb1",
        sop_setup_files: Optional[Dict[str, str]] = None
    ):
        """
        Initialize test configuration.
        
        Args:
            test_name: Name of the test (e.g., "v2x", "dtc")
            log_file: Path to log file
            adb_cmd: ADB command (default: "adb1")
            sop_setup_files: Dict mapping local paths to remote paths for SOP mode
                            e.g., {"local/sldd": "/log/sldd"}
        """
        self.test_name = test_name
        self.log_file = log_file
        self.adb_cmd = adb_cmd
        self.sop_setup_files = sop_setup_files or {}
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
        require_sop_setup: bool = False
    ):
        """
        Initialize base test.
        
        Args:
            test_name: Name of the test
            log_file: Path to log file
            adb_cmd: ADB command
            sop_setup_files: Files to push for SOP mode
            require_sop_setup: If True, mandatory SOP setup is skipped if not in SOP mode
        """
        self.config = TestConfig(test_name, log_file, adb_cmd, sop_setup_files)
        self.require_sop_setup = require_sop_setup
        
        # Initialize logger and shell
        os.makedirs(os.path.dirname(self.config.log_file) or ".", exist_ok=True)
        self.logger = ADBLogger(log_file=self.config.log_file)
        self.shell = ADBShell(adb_cmd=self.config.adb_cmd, logger=self.logger)
        self.files = ADBFileManager(adb_cmd=self.config.adb_cmd, logger=self.logger)

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
            if hasattr(self, 'shell'):
                self.shell.close()
        except:
            pass

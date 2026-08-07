"""V2X Test - Unified Master/SOP mode"""

try:
    from tests.test_base import TestBase
except ImportError:  # pragma: no cover - fallback for direct script execution
    from test_base import TestBase
from typing import List, Union, Tuple
import time
from framework.adbshell import ADBShell, ADBLogger, ADBFileManager
from framework.helper import Helper
class V2XTest(TestBase):
    """V2X test that works in both Master and SOP modes."""
    
    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
        """V2X test command sequence."""
        return [
            "sldd power requestset 2004 7",
            "sldd power requestset 2004 2",
            "sldd power requestset 2004 5",
            "pgrep -f its",
            "ps -fC its",
            "ps -fC its",
            ("killall its", 20),
            "sldd power requestset 2002 1",
        ]
    
    def setup_custom(self) -> None:
        """V2X-specific setup."""
        if Helper.is_binary_sop(self.config.version_output):
            Helper.sop_mount_remount(self.shell, self.logger)        

        # Step 1: Ask if DLT is open
        Helper.ask("Is DLT open?")
        
        # Step 2: Enable data privacy
        self.shell.run(self._wrap_command("sldd v2xmgr setdataprivacy 1"))
        time.sleep(8)
        
        # Step 3: Start ITS stack (only for ICONSF25 devices)
        if Helper.is_icon_sf25(self.config.version_output):
            self.shell.run("systemctl start its")
            time.sleep(2)
        
        # Step 4: Verify stack is ON before continuing
        Helper.is_stack_on(self.shell, self.logger)
    
    def teardown_custom(self) -> None:
        """V2X-specific cleanup."""
        Helper.ask("Are logs saved?")
        # Disable data privacy (wrapped for SOP mode)
        cmd = self._wrap_command("sldd v2xmgr setdataprivacy 0")
        self.shell.run(cmd)
        self.shell.run("reboot")


def main():
    """Run V2X test."""
    log_file = r"../logs/v2x_test.log"
    test = V2XTest(test_name="V2X Test", log_file=log_file)
    success = test.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())

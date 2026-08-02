"""Diagnostics Test - Unified Master/SOP mode"""

from test_base import TestBase
from typing import List, Union, Tuple
import time
from framework.helper import Helper


class DiagnosticsTest(TestBase):
    """Diagnostics test."""
    
    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
        """Diagnostics test commands."""
        return [
            "sldd v2xmgr readDiag RDBI_V2X_SECURITY",
            "sldd v2xmgr readDiag RDBI_V2X_RADIO",
            "sldd v2xmgr readDiag RDBI_V2X_STACK_CONFIGURATION",
            "sldd v2xmgr readDiag RDBI_V2X_HSM",
            "sldd v2xmgr readDiag RDBI_V2X_COMPENSATOR_LNA",
            "sldd Diag readDid 43a0",
            "sldd Diag writeDid 43A0 00",
            "sldd Diag readDid 43A0",
            "sldd Diag writeDid 43A0 01",
            "sldd Diag readDid 43A0",
        ]
    
    def setup_custom(self) -> None:
        """Diagnostics-specific setup."""
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
        Helper.is_stack_on(self.shell)
    
    def teardown_custom(self) -> None:
        """Diagnostics-specific cleanup."""
        Helper.ask("Are logs saved?")
        # Disable data privacy (wrapped for SOP mode)
        cmd = self._wrap_command("sldd v2xmgr setdataprivacy 0")
        self.shell.run(cmd)


def main():
    """Run Diagnostics test."""
    log_file = r"../logs/diagnostics_test.log"
    test = DiagnosticsTest(test_name="Diagnostics Test", log_file=log_file)
    success = test.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())

"""DTC (Diagnostic Trouble Code) Test - Unified Master/SOP mode"""

from test_base import TestBase
from typing import List, Union, Tuple
import time
from framework.helper import Helper


class DTCTest(TestBase):
    """DTC test that works in both Master and SOP modes."""
    
    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
        """
        DTC test commands.
        Most of the work is done in setup_custom() for DTC cases.
        """
        return []
    
    def setup_custom(self) -> None:
        """DTC-specific setup and test cases."""
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
        
        # DTC test cases
        test_cases = [
            ("TC1: V2X PKI Client: Authorization request failed", "PKI_ERROR_AUTH_REQ_FAILED"),
            ("TC2: V2X PKI Client: Update certificate list failed", "PKI_ERROR_CERT_LIST_UPDATE_FAILED"),
            ("TC3: V2X PKI Client: Unable to connect to V2X SW stack", "PKI_ERROR_V2X_STACK_CONNECTION_ERROR"),
            ("TC4: V2X PKI Client: Unable to connect to V2X PKI server", "PKI_ERROR_PKI_SERVER_CONNECTION_ERROR"),
            ("TC5: V2X PKI Client: File system access error", "PKI_ERROR_FS_ACCESS_ERROR"),
            ("TC6: V2X PKI Client: Enrollment failed", "PKI_ERROR_ENROLLMENT_FAILED"),
            ("TC7: V2X PKI Client: Authorization download failed", "PKI_ERROR_AUTH_DOWNLOAD_FAILED"),
            ("TC8: V2X PKI Client: Enrollment renewal failed", "PKI_ERROR_REENROLLMENT_FAILED"),
            ("TC9: V2X SW Stack: ECDSA accelerator access error", "STACK_ERROR_ECDSA_ACCESS_ERROR"),
            ("TC10: V2X SW Stack: File system access error", "STACK_ERROR_FS_ACCESS_ERROR"),
            ("TC11: V2X SW Stack: HSM access error", "STACK_ERROR_HSM_ACCESS_ERROR"),
            ("TC12: V2X SW Stack: Missing V2X authorization certificate", "STACK_ERROR_MISSING_AUTH_CERT"),
            ("TC13: V2X SW Stack: Missing V2X certificate list", "STACK_ERROR_MISSING_CERT_LIST"),
        ]
        
        for desc, code in test_cases:
            self.logger.log(f"\n{desc}")
            time.sleep(5)
            
            # Set DTC
            cmd_set = f"sldd v2xmgr setDTC {code} 1"
            self.shell.run(self._wrap_command(cmd_set))
            time.sleep(3)
            
            # Clear DTC
            cmd_clear = f"sldd v2xmgr setDTC {code} 0"
            self.shell.run(self._wrap_command(cmd_clear))
            time.sleep(1)
        
        # ===== TC15: V2X function unavailable =====
        self.logger.log("\nTC15: V2X function unavailable")
        time.sleep(1)
        self.logger.log("Stopping ITS stack")
        self.shell.run("systemctl stop its")
        time.sleep(10)
        self.logger.log("Starting ITS stack")
        self.shell.run("systemctl start its")
        time.sleep(5)
        
        # ===== TC16: V2X SW Stack: Missing navigation information =====
        self.logger.log("\nTC16: V2X SW Stack: Missing navigation information")
        time.sleep(1)
        self.shell.run(self._wrap_command("sldd v2xmgr setDTC STACK_ERROR_MISSING_NAV_INFO 1"))
        time.sleep(1)
        self.shell.run(self._wrap_command("sldd v2xmgr setDTC STACK_ERROR_MISSING_NAV_INFO 0"))
        time.sleep(1)
        
        # ===== TC17: V2X SW Stack: Missing map information =====
        self.logger.log("\nTC17: V2X SW Stack: Missing map information")
        time.sleep(1)
        self.shell.run(self._wrap_command("sldd v2xmgr setDTC STACK_ERROR_MISSING_MAP_INFO 1"))
        time.sleep(1)
        self.shell.run(self._wrap_command("sldd v2xmgr setDTC STACK_ERROR_MISSING_MAP_INFO 0"))
        time.sleep(1)
        
        # ===== TC18: V2X SW Stack: V2X radio access error =====
        self.logger.log("\nTC18: V2X SW Stack: V2X radio access error")
        self.logger.log("Device may reboot in this Test Case")
        count = 4
        for current in range(count):
            self.logger.log(f"Radio access error attempt {current + 1}/{count}")
            time.sleep(10)
            self.shell.run(self._wrap_command("sldd v2xmgr setDTC STACK_ERROR_RADIO_ACCESS_ERROR 1"))
            time.sleep(10)
        
        # ===== TC14: V2X deactivated by diagnosis =====
        self.logger.log("\nTC14: V2X deactivated by diagnosis")
        time.sleep(1)
        self.shell.run(self._wrap_command("sldd Diag writeDid 43A0 00"))
        time.sleep(10)
        self.logger.log("Restoring DID 43A0 to 01")
        self.shell.run(self._wrap_command("sldd Diag writeDid 43A0 01"))
        time.sleep(5)
        
        time.sleep(1)
        self.logger.log("Rebooting device...")
        self.shell.run("reboot")
        time.sleep(1) 
    
    def teardown_custom(self) -> None:
        """DTC-specific cleanup all 18 test cases."""
        Helper.ask("Are logs saved?")
        
        # Disable data privacy (wrapped for SOP mode)
        cmd = self._wrap_command("sldd v2xmgr setdataprivacy 0")
        self.shell.run(cmd)


def main():
    """Run DTC test."""
    log_file = r"../logs/dtc_testcases.log"
    test = DTCTest(test_name="DTC Test", log_file=log_file)
    success = test.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())

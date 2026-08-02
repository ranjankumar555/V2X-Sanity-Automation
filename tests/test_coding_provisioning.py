"""Coding Provisioning Test - Unified Master/SOP mode"""

from test_base import TestBase
from typing import List, Union, Tuple
import time
from framework.helper import Helper


class CodingProvisioningTest(TestBase):
    """Coding Provisioning test."""
    
    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
        """Coding Provisioning test commands."""
        return [
            "sldd cfg reload 2 0 /data/config-service/prov.xml",
            "sldd cfg reload 0 0 /data/config-service/coding.txt",
            "sldd cfg reload 0 0 /data/config-service/coding.txt",
            "sldd cfg reload 0 0 /data/config-service/coding.txt",
        ]
    
    def setup_custom(self) -> None:
        """Coding Provisioning-specific setup."""
        if Helper.is_binary_sop(self.config.version_output):
            Helper.sop_mount_remount(self.shell, self.logger)
        # Step 1: smack_admin because prov.xml needs to be pushed to /data/config-service/ which is protected
        if not Helper.is_binary_sop(self.config.version_output):
            self.shell.run("smack_admin")
            self.shell.run("echo -> /sys/fs/smackfs/onlycap")
            
            # exit from smack_admin shell
            self.shell.run("exit")
            if Helper.is_region_eu(self.files, self.logger):  # Log detected region
                self.files.push(r"D:\Cybersecurity\Snake Oil EU\EU_Prov_File\prov.xml", "/data/config-service/")
            else:
                self.files.push(r"D:\Cybersecurity\Snake Oil CN\CN_Prov_File\prov.xml", "/data/config-service/")
        
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
        """Coding Provisioning-specific cleanup."""
        Helper.ask("Are logs saved?")
        # Disable data privacy (wrapped for SOP mode)
        cmd = self._wrap_command("sldd v2xmgr setdataprivacy 0")
        self.shell.run(cmd)


def main():
    """Run Coding Provisioning test."""
    log_file = r"../logs/coding_prov_test.log"
    test = CodingProvisioningTest(test_name="Coding Provisioning Test", log_file=log_file)
    success = test.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())

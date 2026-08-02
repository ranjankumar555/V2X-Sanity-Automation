"""Cybersecurity Test - Unified Master/SOP mode with region support"""

from test_base import TestBase
from typing import List, Union, Tuple
import time
from framework.helper import Helper


class CybersecurityTest(TestBase):
    """Cybersecurity test with EU/CN region support."""
    
    # File paths for cybersecurity prerequisites
    EU_CERT_PATH = r"D:\Cybersecurity\Snake oil EU\signer_1_EU\."
    EU_CN_FILE_PATH = r"D:\Cybersecurity\pushfile_data_v2xmgr_etc\."
    REMOTE_PATH = "/data/v2xmgr/etc/"
    
    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
        """No initial commands; region-specific tests in setup_custom."""
        return []
    
    def setup_custom(self) -> None:
        """Cybersecurity-specific setup with region tests."""
        if Helper.is_binary_sop(self.config.version_output):
            Helper.sop_mount_remount(self.shell, self.logger)
        Helper.sop_mount_remount(self.shell, self.logger, path="/data/")
        # ===== STEP 1: Push necessary files and folders (ONE TIME) =====
        self.logger.log("\n=== Initial Setup: Pushing Files ===\n")
        
        # Push common cybersecurity files
        self.files.push_folder(self.EU_CN_FILE_PATH, self.REMOTE_PATH)
        
        # Create MBD directory and push EU certificates
        self.shell.run("mkdir -p /data/v2xmgr/etc/MBD")
        self.files.push_folder(self.EU_CERT_PATH, "/data/v2xmgr/etc/MBD/")
        
        # Set permissions on MBD directory
        # self.shell.run("chmod 777 /data/v2xmgr/etc/MBD/*")
        
        # Rename rio_inject.txt to rio_inject and set permissions
        self.shell.run("mv /data/v2xmgr/etc/rio_inject.txt /data/v2xmgr/etc/rio_inject")
        # self.shell.run("chmod 777 /data/v2xmgr/etc/rio_inject /data/v2xmgr/etc/*.bin")
        self.shell.run("chmod 777 /data/v2xmgr/etc/rio_inject")
        
        # Verify all files
        self.shell.run("ls -l /data/v2xmgr/etc/")
        self.logger.log("\n=== Files and permissions verified ===\n")

        # ===== STEP 2: Ask if DLT is open =====
        Helper.ask("Is DLT open?")
        
        # Define test commands for each region
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
        
        # ===== STEP 3: Detect initial region and run both region tests =====
        if Helper.is_region_eu(self.files, self.logger):
            # First region: EU, then switch to CN
            self._test_region("EU", commands_EU, is_first_region=True)
            cmd = self._wrap_command("sldd v2xmgr changeregion cn")
            self.shell.run(cmd)
            self._test_region("CN", commands_CN, is_first_region=False)
        else:
            # First region: CN, then switch to EU
            self._test_region("CN", commands_CN, is_first_region=True)
            cmd = self._wrap_command("sldd v2xmgr changeregion eu")
            self.shell.run(cmd)
            self._test_region("EU", commands_EU, is_first_region=False)
    
    def teardown_custom(self) -> None:
        """Cybersecurity-specific cleanup (stack management handled in setup_custom)."""
        # Stack is already deactivated at the end of each region test in setup_custom
        pass
    
    def _test_region(self, region: str, commands: List[str], is_first_region: bool = False) -> None:
        """Execute complete test cycle for a region: modify config → activate → test → deactivate.
        
        Args:
            region: "EU" or "CN"
            commands: List of test commands to run
            is_first_region: If False, handles region change verification before testing
        """
        # Modify cybersecurity config for this region
        Helper.modify_its_cybersecurity(self.shell, self.files, self.logger)
        
        # For second region, verify the region change was successful
        if not is_first_region:
            Helper.ask(f"Is device rebooted and region changed to {region}?")
            
            # Verify region actually changed
            region_is_eu = Helper.is_region_eu(self.files, self.logger)
            if (region == "EU" and not region_is_eu) or (region == "CN" and region_is_eu):
                self.logger.log(f"[WARNING] Region did not change to {region}, skipping test")
                return
        
        # Activate stack
        cmd = self._wrap_command("sldd v2xmgr setdataprivacy 1")
        self.shell.run(cmd)
        time.sleep(8)
        
        is_sf25 = Helper.is_icon_sf25(self.config.version_output)
        
        if is_sf25 is None:
            self.logger.log("[INFO] SF25 detection inconclusive; attempting fallback detection...")
            diag = Helper.detect_device_type(self.shell, self.logger)
            is_sf25 = diag.get("is_sf25", False) or False
        
        if is_sf25:
            self.logger.log("[INFO] ICON SF25 detected, starting ITS service")
            self.shell.run("systemctl start its")
            time.sleep(3)
        else:
            self.logger.log(f"[INFO] ICON SF25 not detected from version output: {self.config.version_output!r}")
        
        Helper.is_stack_on(self.shell, self.logger)
        
        # Run region-specific tests
        self.logger.log(f"\n=== Starting Cybersecurity_{region} Test ===\n")
        for cmd in commands:
            # rio_inject is not an sldd command, so it's not wrapped
            self.shell.run(cmd)
            time.sleep(2)
        self.logger.log(f"\n=== Cybersecurity_{region} Test Completed ===\n")
        
        # Ask if logs saved
        Helper.ask("Are logs saved?")
        
        # Deactivate stack
        cmd = self._wrap_command("sldd v2xmgr setdataprivacy 0")
        self.shell.run(cmd)
        time.sleep(2)


def main():
    """Run Cybersecurity test."""
    log_file = r"../logs/cybersecurity_test.log"
    test = CybersecurityTest(test_name="Cybersecurity Test", log_file=log_file)
    success = test.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())

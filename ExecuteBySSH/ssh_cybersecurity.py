"""SSH-backed Cybersecurity test wrapper.
"""
import os
import sys
from typing import List, Union, Tuple
import time

PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from tests.test_base import SSHTestBase
from framework.helper import Helper


class SSHCybersecurityTest(SSHTestBase):
    EU_CERT_PATH = r"D:\Cybersecurity\Snake oil EU\signer_1_EU\."
    EU_CN_FILE_PATH = r"D:\Cybersecurity\pushfile_data_v2xmgr_etc\."
    REMOTE_PATH = "/data/v2xmgr/etc/"

    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
        return []

    def setup_custom(self) -> None:
        if Helper.is_binary_sop(self.config.version_output):
            Helper.sop_mount_remount(self.shell, self.logger)
        Helper.sop_mount_remount(self.shell, self.logger, path="/data/")

        self.logger.log("\n=== Initial Setup: Pushing Files ===\n")
        self.files.push_folder(self.EU_CN_FILE_PATH, self.REMOTE_PATH)
        self.shell.run("mkdir -p /data/v2xmgr/etc/MBD")
        self.files.push_folder(self.EU_CERT_PATH, "/data/v2xmgr/etc/MBD/")
        self.shell.run("mv /data/v2xmgr/etc/rio_inject.txt /data/v2xmgr/etc/rio_inject")
        self.shell.run("chmod 777 /data/v2xmgr/etc/rio_inject")
        self.shell.run("ls -l /data/v2xmgr/etc/")

        Helper.ask("Is DLT open?")
        commands_EU = [
            "/data/v2xmgr/etc/rio_inject 1 127.0.0.1 /data/v2xmgr/etc/invalid_signature_cam.bin",
            "/data/v2xmgr/etc/rio_inject 1 127.0.0.1 /data/v2xmgr/etc/valid_cam.bin",
        ]
        commands_CN = [
            "/data/v2xmgr/etc/rio_inject 4 127.0.0.1 /data/v2xmgr/etc/invalid_signature_cn_bsm.bin",
            "/data/v2xmgr/etc/rio_inject 4 127.0.0.1 /data/v2xmgr/etc/valid_cn_bsm.bin",
        ]

        if Helper.is_region_eu(self.files, self.logger):
            self._test_region("EU", commands_EU, is_first_region=True)
            cmd = self._wrap_command("sldd v2xmgr changeregion cn")
            self.shell.run(cmd)
            self._test_region("CN", commands_CN, is_first_region=False)
        else:
            self._test_region("CN", commands_CN, is_first_region=True)
            cmd = self._wrap_command("sldd v2xmgr changeregion eu")
            self.shell.run(cmd)
            self._test_region("EU", commands_EU, is_first_region=False)

    def teardown_custom(self) -> None:
        pass

    def _test_region(self, region: str, commands: List[str], is_first_region: bool = False) -> None:
        Helper.modify_its_cybersecurity(self.shell, self.files, self.logger)
        if not is_first_region:
            Helper.ask(f"Is device rebooted and region changed to {region}?")
            region_is_eu = Helper.is_region_eu(self.files, self.logger)
            if (region == "EU" and not region_is_eu) or (region == "CN" and region_is_eu):
                self.logger.log(f"[WARNING] Region did not change to {region}, skipping test")
                return

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

        self.logger.log(f"\n=== Starting Cybersecurity_{region} Test ===\n")
        for cmd in commands:
            self.shell.run(cmd)
            time.sleep(2)
        self.logger.log(f"\n=== Cybersecurity_{region} Test Completed ===\n")

        Helper.ask("Are logs saved?")
        cmd = self._wrap_command("sldd v2xmgr setdataprivacy 0")
        self.shell.run(cmd)
        time.sleep(2)


if __name__ == "__main__":
    log_file = r"../logs/cybersecurity_test.log"
    test = SSHCybersecurityTest(test_name="Cybersecurity Test", log_file=log_file)
    success = test.run()
    raise SystemExit(0 if success else 1)

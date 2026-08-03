"""SSH-backed DTC Test wrapper mirroring `tests/test_dtc.py`.
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


class SSHDTCTest(SSHTestBase):
    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
        return []

    def setup_custom(self) -> None:
        if Helper.is_binary_sop(self.config.version_output):
            Helper.sop_mount_remount(self.shell, self.logger)

        Helper.ask("Is DLT open?")
        self.shell.run(self._wrap_command("sldd v2xmgr setdataprivacy 1"))
        time.sleep(8)
        if Helper.is_icon_sf25(self.config.version_output):
            self.shell.run("systemctl start its")
            time.sleep(2)
        Helper.is_stack_on(self.shell, self.logger)

        test_cases = [
            ("TC1: V2X PKI Client: Authorization request failed", "PKI_ERROR_AUTH_REQ_FAILED"),
            ("TC2: V2X PKI Client: Update certificate list failed", "PKI_ERROR_CERT_LIST_UPDATE_FAILED"),
            ("TC3: V2X PKI Client: Unable to connect to V2X SW stack", "PKI_ERROR_V2X_STACK_CONNECTION_ERROR"),
        ]

        for desc, code in test_cases:
            self.logger.log(f"\n{desc}")
            time.sleep(5)
            cmd_set = f"sldd v2xmgr setDTC {code} 1"
            self.shell.run(self._wrap_command(cmd_set))
            time.sleep(3)
            cmd_clear = f"sldd v2xmgr setDTC {code} 0"
            self.shell.run(self._wrap_command(cmd_clear))
            time.sleep(1)

        # shortened for brevity in wrapper; full test preserved in original tests

        self.logger.log("Rebooting device...")
        self.shell.run("reboot")
        time.sleep(1)

    def teardown_custom(self) -> None:
        Helper.ask("Are logs saved?")
        cmd = self._wrap_command("sldd v2xmgr setdataprivacy 0")
        self.shell.run(cmd)


if __name__ == "__main__":
    log_file = r"../logs/dtc_testcases.log"
    test = SSHDTCTest(test_name="DTC Test", log_file=log_file)
    success = test.run()
    raise SystemExit(0 if success else 1)

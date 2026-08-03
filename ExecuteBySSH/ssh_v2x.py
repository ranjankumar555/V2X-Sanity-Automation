"""SSH-backed V2X Test wrapper mirroring `tests/test_v2x.py`.

This wrapper uses SSHTestBase, which will attempt SSH and/or ADB transports.
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


class SSHV2XTest(SSHTestBase):
    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
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
        if Helper.is_binary_sop(self.config.version_output):
            Helper.sop_mount_remount(self.shell, self.logger)

        Helper.ask("Is DLT open?")
        Helper.activate_stack(self.shell, self.logger)

    def teardown_custom(self) -> None:
        Helper.ask("Are logs saved?")
        cmd = self._wrap_command("sldd v2xmgr setdataprivacy 0")
        self.shell.run(cmd)
        self.shell.run("reboot")


if __name__ == "__main__":
    log_file = r"../logs/v2x_test.log"
    test = SSHV2XTest(test_name="V2X Test", log_file=log_file)
    success = test.run()
    raise SystemExit(0 if success else 1)

"""SSH-backed Cybersecurity test wrapper.

This wrapper inherits the existing Cybersecurity test workflow and adds SSH
transport initialization through SSHTestBase.
"""
import os
import sys

PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from tests.test_base import SSHTestBase
from tests.test_cybersecurity import CybersecurityTest


class SSHCybersecurityTest(CybersecurityTest, SSHTestBase):
    def __init__(
        self,
        test_name: str,
        log_file: str,
        ssh_host=None,
        ssh_user="root",
        ssh_key_file=None,
        ssh_password=None,
        ssh_port=22,
        accept_host_key=True,
        adb_cmd="adb1",
        use_adb: bool = True,
    ):
        super().__init__(
            test_name=test_name,
            log_file=log_file,
            ssh_host=ssh_host,
            ssh_user=ssh_user,
            ssh_key_file=ssh_key_file,
            ssh_password=ssh_password,
            ssh_port=ssh_port,
            accept_host_key=accept_host_key,
            adb_cmd=adb_cmd,
            use_adb=use_adb,
        )


if __name__ == "__main__":
    log_file = r"../logs/cybersecurity_test.log"
    test = SSHCybersecurityTest(test_name="Cybersecurity Test", log_file=log_file)
    success = test.run()
    raise SystemExit(0 if success else 1)

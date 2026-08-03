"""SSH-backed Basic Sanity test wrapper.

This adapts tests/basic_sanity.py to run using SSH-based shell and file manager.
"""
import os
import sys

PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from tests.test_base import SSHTestBase
from tests.basic_sanity import BasicSanityTest


class SSHBasicSanityTest(BasicSanityTest, SSHTestBase):
    # MRO note: BasicSanityTest defines the actual test workflow and
    # shell.run() usage. SSHTestBase provides the transport layer and
    # initializes self.shell/self.files before the shared test logic
    # executes. Thus calls in BasicSanityTest use SSH/ADB via SSHTestBase.
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
    log_file = r"../logs/basic_sanity.log"
    test = SSHBasicSanityTest(test_name="Basic Sanity Test", log_file=log_file)
    success = test.run()
    raise SystemExit(0 if success else 1)

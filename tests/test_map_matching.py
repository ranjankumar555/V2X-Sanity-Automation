"""Map Matching Test - Unified Master/SOP mode"""

from test_base import TestBase
from typing import List, Union, Tuple
import time

class MapMatchingTest(TestBase):
    """Map Matching test."""
    
    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
        """No initial commands; tests in setup_custom."""
        return []
    
    def setup_custom(self) -> None:
        """Map Matching-specific setup with per-region tests."""
        if self.helper.is_binary_sop(self.config.version_output):
            self.helper.sop_mount_remount(self.shell, self.logger)

        # ===== STEP 1: Ask if DLT is open =====
        self.helper.ask("Is DLT open?")
        self.helper.ask("Ensure Postype[7] in DLT")
        
        # ===== STEP 3: Define region-specific commands =====
        commands_EU = []
        commands_CN = []
        
        # ===== STEP 4: Detect current region and run both region tests =====
        if self.helper.is_region_eu(self.files, self.logger):
            # First region: EU, then switch to CN
            self._test_region("EU", commands_EU, is_first_region=True)
            self.helper.ask("Changing region to CN")
            cmd = self._wrap_command("sldd v2xmgr changeregion cn")
            self.shell.run(cmd)
            self._test_region("CN", commands_CN, is_first_region=False)
        else:
            # First region: CN, then switch to EU
            self._test_region("CN", commands_CN, is_first_region=True)
            self.helper.ask("Changing region to EU")
            cmd = self._wrap_command("sldd v2xmgr changeregion eu")
            self.shell.run(cmd)
            self._test_region("EU", commands_EU, is_first_region=False)
    
    def _test_region(self, region: str, commands: List[Tuple[str, int]], is_first_region: bool = False) -> None:
        """Execute complete test cycle for a region: activate stack → test → deactivate.
        
        Args:
            region: "EU" or "CN"
            commands: List of (command, delay) tuples to run
            is_first_region: If False, handles region change verification before testing
        """
        # Run region-specific tests
        self.logger.log(f"\n=== Starting MapMatching_{region} Test ===\n")

        # For second region, verify the region change was successful
        region_is_eu = self.helper.is_region_eu(self.files, self.logger)
        if not is_first_region:
            
            # Verify region actually changed
            if (region == "EU" and not region_is_eu) or (region == "CN" and region_is_eu):
                self.logger.log(f"[WARNING] Region did not change to {region}, skipping test")
                return
            
        # ===== STEP 2: Modify map matching config (ONE TIME) =====
        self.helper.modify_cff_mapmatching(self.shell, self.files, self.logger)
        self.helper.modify_its_ofwd(self.shell, self.files, self.logger)
            
        if region_is_eu :
            self.helper.ask("Ensure VN4610 is connected")
        else :
            self.helper.ask("Ensure PPS sync is available")
        
        # Activate stack
        self.helper.activate_stack(self)
        # self.helper.ask(f"Testing through CANoe? -> Run {region} CANoe config")
        
        # for cmd, delay in commands:
        #     self.shell.run(self._wrap_command(cmd))
        #     time.sleep(delay)
        
        # Ask if logs saved
        self.helper.ask("Are logs saved?")
        
        # Deactivate stack
        cmd = self._wrap_command("sldd v2xmgr setdataprivacy 0")
        self.shell.run(cmd)
        time.sleep(2)
    
    def teardown_custom(self) -> None:
        """Map Matching-specific cleanup (stack management handled in setup_custom)."""
        pass


def main():
    """Run Map Matching test."""
    log_file = r"../logs/map_matching.log"
    test = MapMatchingTest(test_name="Map Matching Test", log_file=log_file)
    success = test.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())


"""Geofencing Test - Unified Master/SOP mode with region support"""

from test_base import TestBase
from typing import List, Union, Tuple
import time
from framework.adbshell import Helper
class GeofencingTest(TestBase):
    """Geofencing test with region support."""
    
    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
        """No initial commands; tests in setup_custom."""
        return []
    
    def setup_custom(self) -> None:
        """Geofencing-specific setup with per-region tests."""
        if Helper.is_binary_sop(self.config.version_output):
            Helper.setup_sop_prerequisites(self.shell, self.files, self.logger)
        """Geofencing-specific setup with per-region tests."""
        
        # ===== STEP 3: Define region-specific commands =====
        commands_EU = [
            ("sldd v2xmgr setGeofencingCountry 276", 2),
        ]
        commands_CN = [
            ("sldd v2xmgr setGeofencingCountry 156", 2),
        ]
        
        # ===== STEP 4: Detect current region and run both region tests =====
        if Helper.is_region_eu(self.files, self.logger):
            # First region: EU, then switch to CN
            self._test_region("EU", commands_EU, is_first_region=True)
            Helper.ask("Change region to CN")
            cmd = self._wrap_command("sldd v2xmgr changeregion cn")
            self.shell.run(cmd)
            self._test_region("CN", commands_CN, is_first_region=False)
        else:
            # First region: CN, then switch to EU
            self._test_region("CN", commands_CN, is_first_region=True)
            Helper.ask("Change region to EU")
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
        self.logger.log(f"\n=== Starting Geofencing_{region} Test ===\n")
        # ===== Modify geofencing config (ONE TIME) =====
        Helper.modify_its_geofencing(self.shell, self.files, self.logger)
        Helper.disable_map_matching_for_geofencing_in_cff(self.shell, self.files, self.logger)

        # Run region-specific tests
        Helper.ask(f"Set STATIC + LOCATION in GNSS Simulator")
        Helper.ask("Confirm 3D FIX available")

        # ===== STEP 1: Ask if DLT is open =====
        Helper.ask("Is DLT opened?")

        # Set the country code for geofencing
        for cmd, delay in commands:
            self.shell.run(self._wrap_command(cmd))
            time.sleep(delay)

        # Activate ITS stack
        Helper.activate_stack(self)
        
        # Ask if logs saved
        Helper.ask("Are logs saved?")
        
        # Deactivate ITS stack
        cmd = self._wrap_command("sldd v2xmgr setdataprivacy 0")
        self.shell.run(cmd)
        time.sleep(2)

         # For second region, verify the region change was successful
        if not is_first_region:
            Helper.ask(f"Is device rebooted and region changed to {region}?")
    
    def teardown_custom(self) -> None:
        """Geofencing-specific cleanup (stack management handled in setup_custom)."""
        pass


def main():
    """Run Geofencing test."""
    log_file = r"../logs/geofencing.log"
    test = GeofencingTest(test_name="Geofencing Test", log_file=log_file)
    success = test.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())

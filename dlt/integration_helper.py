#!/usr/bin/env python3
"""
Integration Helper: Use test_base.py version_output with DLT Verification

This module provides utilities to integrate the DLT verification system with
the test_base.py TestBase class, using self.config.version_output.

Example Usage in TestBase Subclass:

    from tests.test_base import TestBase
    from dlt.integration_helper import DLTIntegrationHelper
    
    class MyV2XTest(TestBase):
        def teardown_custom(self):
            # Auto-create versioned directory and log location info
            helper = DLTIntegrationHelper(self.config.version_output)
            info = helper.get_setup_info()
            
            self.logger.log(f"DLT Verification Setup:")
            self.logger.log(f"  Version: {info['version']}")
            self.logger.log(f"  Expected Location: {info['dlt_location']}")
            self.logger.log(f"  CSV Location: {info['csv_location']}")
            self.logger.log(f"  Verification Command: {info['verify_command']}")
"""

import sys
from pathlib import Path
from typing import Dict, Optional
from dlt.version_parser import VersionParser
from dlt.dlt_verifier import DLTVerifier


class DLTIntegrationHelper:
    """Helper class to integrate DLT verification with test_base.py"""
    
    def __init__(self, version_output: str, base_path: str = "logs/sanity"):
        """
        Initialize integration helper.
        
        Args:
            version_output: Device version from test_base.config.version_output
                          (e.g., "v040.040.065.iconsf25.oem_260525")
            base_path: Base directory for organized DLT logs
        """
        self.version_output = version_output.strip() if version_output else None
        self.base_path = base_path
        
        if self.version_output:
            self.parser = VersionParser(self.version_output)
        else:
            self.parser = None
    
    def is_version_valid(self) -> bool:
        """Check if version was successfully parsed."""
        if not self.parser:
            return False
        
        return (self.parser.date != "unknown" and 
                self.parser.device_variant != "unknown")
    
    def create_directory(self) -> Optional[Path]:
        """
        Create version-specific directory.
        
        Returns:
            Path object if successful, None if version invalid
        """
        if not self.is_version_valid():
            return None
        
        return Path(DLTVerifier.create_version_directory(
            self.version_output, 
            self.base_path
        ))
    
    def get_setup_info(self) -> Dict[str, str]:
        """
        Get setup information for test completion.
        
        Returns:
            Dict with version, paths, and commands for DLT verification
        """
        info = {
            "version": self.version_output or "unknown",
            "valid": self.is_version_valid(),
            "base_path": self.base_path,
            "date": self.parser.date if self.parser else "unknown",
            "variant": self.parser.device_variant if self.parser else "unknown",
            "dlt_location": "N/A",
            "csv_location": "N/A",
            "verify_command": "N/A",
            "auto_verify_command": "N/A",
        }
        
        if self.is_version_valid():
            version_dir = self.parser.get_directory_path(self.base_path)
            
            info["dlt_location"] = str(
                version_dir / self.parser.get_expected_dlt_filename()
            )
            info["csv_location"] = str(
                version_dir / f"basic_sanity_{self.version_output}.csv"
            )
            info["verify_command"] = (
                f"python dlt\\dlt_quick_verify.py "
                f'"{info["csv_location"]}" "{self.version_output}"'
            )
            info["auto_verify_command"] = (
                f"python dlt\\dlt_quick_verify.py --auto-verify "
                f'"{self.version_output}" "{self.base_path}"'
            )
        
        return info
    
    def format_setup_message(self) -> str:
        """
        Format a human-readable setup message for test logs.
        
        Returns:
            Formatted message with DLT verification steps
        """
        info = self.get_setup_info()
        
        lines = [
            "\n" + "="*70,
            "DLT VERIFICATION SETUP",
            "="*70,
            f"Device Version: {info['version']}",
            f"Status:         {'✓ Valid' if info['valid'] else '✗ Invalid'}",
        ]
        
        if info['valid']:
            lines.extend([
                f"Date:           {info['date']}",
                f"Variant:        {info['variant']}",
                "",
                "NEXT STEPS:",
                "1. Copy DLT file to:",
                f"   {info['dlt_location']}",
                "",
                "2. Export DLT to CSV using DLT Viewer",
                f"   Save as: {info['csv_location']}",
                "",
                "3. Run verification:",
                f"   {info['verify_command']}",
                "",
                "OR use auto-verify (if CSV exists):",
                f"   {info['auto_verify_command']}",
            ])
        else:
            lines.extend([
                "",
                "⚠ Version format not recognized",
                f"Expected: v{{major}}.{{minor}}.{{patch}}.{{variant}}.oem_{{date}}",
                f"Got:      {info['version']}",
            ])
        
        lines.append("="*70 + "\n")
        return "\n".join(lines)
    
    def get_verify_command(self, use_auto: bool = False) -> Optional[str]:
        """
        Get verification command string.
        
        Args:
            use_auto: If True, return auto-verify command
        
        Returns:
            Python command string or None
        """
        info = self.get_setup_info()
        
        if use_auto:
            return info.get("auto_verify_command")
        else:
            return info.get("verify_command")


def integrate_with_testbase_example():
    """
    Example of how to integrate DLTIntegrationHelper with TestBase.
    
    This shows the recommended pattern for test_base.py subclasses.
    """
    example_code = '''
# In your test class that extends TestBase:

from dlt.integration_helper import DLTIntegrationHelper

class MyV2XTest(TestBase):
    def teardown_custom(self):
        """Log DLT verification setup after test completes."""
        
        # Create integration helper with version from test config
        helper = DLTIntegrationHelper(
            self.config.version_output,
            base_path="logs/sanity"
        )
        
        # Create versioned directory
        version_dir = helper.create_directory()
        if version_dir:
            self.logger.log(f"✓ Version directory created: {version_dir}")
        
        # Log setup instructions
        self.logger.log(helper.format_setup_message())
        
        # Optionally save setup info to file
        info = helper.get_setup_info()
        import json
        setup_file = version_dir / "dlt_setup_info.json"
        with open(setup_file, "w") as f:
            json.dump(info, f, indent=2)
'''
    
    return example_code


if __name__ == "__main__":
    # Example usage
    test_version = "v040.040.065.iconsf25.oem_260525"
    
    helper = DLTIntegrationHelper(test_version, "D:\\SANITY")
    
    print("Integration Helper Demo")
    print("="*70)
    print(f"\nVersion: {test_version}")
    print(f"Valid: {helper.is_version_valid()}")
    
    print("\nSetup Information:")
    info = helper.get_setup_info()
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    print(helper.format_setup_message())
    
    print("\nExample Integration Code:")
    print(integrate_with_testbase_example())

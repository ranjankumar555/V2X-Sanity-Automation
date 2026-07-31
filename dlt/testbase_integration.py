#!/usr/bin/env python3
"""
Test Base Integration for Automated DLT Verification

Provides easy integration of automated DLT verification into test_base.py subclasses.

Usage in your test class:

    from tests.test_base import TestBase
    from dlt.testbase_integration import DLTVerificationMixin
    
    class BasicSanityTest(DLTVerificationMixin, TestBase):
        def teardown_custom(self):
            # Auto-verify DLT logs after test
            self.verify_dlt_logs()
    
Or for full control:

    def teardown_custom(self):
        from dlt.testbase_integration import TestBaseDLTHelper
        
        helper = TestBaseDLTHelper(
            version_output=self.config.version_output,
            logger=self.logger,
            cleanup_csv=True  # Auto-delete temp CSV after verification
        )
        
        success = helper.verify()
        if success:
            self.logger.log("✓ All DLT verifications passed")
        else:
            self.logger.log("✗ DLT verification failed")
"""

import sys
import shutil
import time
from pathlib import Path
from typing import Optional, Any
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dlt.auto_dlt_verify import AutoDLTVerifier
from dlt.version_parser import VersionParser


class TestBaseDLTHelper:
    """
    DLT verification helper for test_base.py integration.
    
    Designed to work seamlessly with TestBase classes.
    Handles:
    - Saving DLT files to versioned directories
    - Automatic DLT verification
    - Summary reporting
    """
    
    def __init__(
        self,
        version_output: str,
        logger: Any,
        base_path: str = r"D:\SANITY",
        cleanup_csv: bool = True
    ):
        """
        Initialize DLT helper for TestBase.
        
        Args:
            version_output: Device version from self.config.version_output
            logger: Logger instance from self.logger
            base_path: Base path for organized DLT logs
            cleanup_csv: If True, delete temporary CSV after verification
        """
        self.version_output = version_output
        self.logger = logger
        self.base_path = base_path
        self.cleanup_csv = cleanup_csv
        self.dlt_file = None
        self.dlt_saved_path = None
        self.verification_success = False
        
        self.verifier = AutoDLTVerifier(
            version_output=version_output,
            logger=logger,
            base_path=base_path
        )
        
        # Parse version for directory operations
        try:
            self.version_parser = VersionParser(version_output.strip()) if version_output else None
        except Exception as e:
            self.logger.log_error(f"Failed to parse version: {e}")
            self.version_parser = None
    
    def save_dlt_file(self, source_dlt_path: str, test_name: str = "basic_sanity") -> bool:
        """
        Save DLT file to versioned directory.
        
        Saves to: {base_path}/{date}/{device_variant}/{test_name}_{version}.dlt
        
        Args:
            source_dlt_path: Path to source DLT file on device or local system
            test_name: Test name for filename (default: "basic_sanity")
        
        Returns:
            True if saved successfully
        """
        if not self.version_parser:
            self.logger.log_error("Cannot save DLT file: version not parsed")
            return False
        
        source = Path(source_dlt_path)
        if not source.exists():
            self.logger.log_error(f"Source DLT file not found: {source_dlt_path}")
            return False
        
        try:
            # Create versioned directory
            version_dir = self.version_parser.create_directory(self.base_path)
            
            # Generate filename: basic_sanity_v040.040.065.iconsf25.oem_260525.dlt
            filename = self.version_parser.get_expected_dlt_filename()
            if not filename.startswith(test_name):
                filename = f"{test_name}_{self.version_parser.full_version}.dlt"
            
            dest_path = version_dir / filename
            
            # Copy DLT file
            shutil.copy2(source, dest_path)
            
            self.dlt_file = source
            self.dlt_saved_path = dest_path
            
            self.logger.log(f"✓ DLT file saved to versioned directory:")
            self.logger.log(f"  {dest_path}")
            
            return True
            
        except Exception as e:
            self.logger.log_error(f"Failed to save DLT file: {e}")
            return False
    
    def verify(self) -> bool:
        """
        Run DLT verification with automatic cleanup.
        
        Returns:
            True if all tests passed
        """
        try:
            success = self.verifier.verify()
            self.verification_success = success
            
            # Log summary
            if success:
                self.logger.log("\n" + "="*70)
                self.logger.log("✓ DLT VERIFICATION PASSED")
                self.logger.log("="*70 + "\n")
            else:
                self.logger.log("\n" + "="*70)
                self.logger.log("✗ DLT VERIFICATION FAILED")
                self.logger.log("="*70 + "\n")
            
            return success
        
        except Exception as e:
            self.logger.log_error(f"DLT verification error: {e}")
            return False
    
    def get_summary(self) -> str:
        """Get human-readable summary of verification results."""
        if not self.verifier.results:
            return "No verification results available"
        
        lines = ["DLT Verification Summary:"]
        
        for test_name, result in self.verifier.results.items():
            status_symbol = "✓" if result.status == "Pass" else "✗"
            lines.append(f"  {status_symbol} {test_name}: {result.status}")
            
            if result.details:
                lines.append(f"     {result.details}")
        
        return "\n".join(lines)
    
    def get_comprehensive_report(self) -> str:
        """
        Get comprehensive test and DLT verification report.
        
        Returns:
            Multi-line formatted report string
        """
        report_lines = []
        
        report_lines.append("\n" + "="*70)
        report_lines.append("TEST SUMMARY & DLT VERIFICATION REPORT")
        report_lines.append("="*70)
        
        # Device Information
        report_lines.append("\n[DEVICE INFORMATION]")
        if self.version_parser:
            report_lines.append(f"  Version: {self.version_parser.full_version}")
            report_lines.append(f"  Device: {self.version_parser.device_variant}")
            report_lines.append(f"  Date: {self.version_parser.date}")
        else:
            report_lines.append(f"  Version: {self.version_output}")
        
        # DLT File Status
        if self.dlt_saved_path:
            report_lines.append("\n[DLT FILE]")
            report_lines.append(f"  Status: ✓ Saved to versioned directory")
            report_lines.append(f"  Path: {self.dlt_saved_path}")
        else:
            report_lines.append("\n[DLT FILE]")
            report_lines.append(f"  Status: ⚠ Not saved to versioned directory")
        
        # DLT Verification Status
        report_lines.append("\n[DLT VERIFICATION]")
        if self.verification_success:
            report_lines.append(f"  Status: ✓ PASSED")
        else:
            report_lines.append(f"  Status: ✗ FAILED or NOT RUN")
        
        # Verification Details
        if self.verifier.results:
            report_lines.append("\n  Verification Details:")
            for test_name, result in self.verifier.results.items():
                status_symbol = "✓" if result.status == "Pass" else "✗"
                report_lines.append(f"    {status_symbol} {test_name}: {result.status}")
                if result.details:
                    report_lines.append(f"       {result.details}")
        
        # Overall Summary
        report_lines.append("\n[OVERALL RESULT]")
        if self.verification_success and self.dlt_saved_path:
            report_lines.append("  ✅ TEST COMPLETED SUCCESSFULLY")
            report_lines.append("     • All test phases executed")
            report_lines.append("     • DLT file saved to versioned directory")
            report_lines.append("     • All verifications PASSED")
        elif self.verification_success:
            report_lines.append("  ⚠️  TESTS PASSED (DLT not saved)")
            report_lines.append("     • Test phases executed successfully")
            report_lines.append("     • Verifications PASSED")
            report_lines.append("     • DLT file not saved to versioned directory")
        else:
            report_lines.append("  ❌ VERIFICATION FAILED")
            report_lines.append("     • Review DLT verification errors above")
        
        report_lines.append("\n" + "="*70 + "\n")
        
        return "\n".join(report_lines)


class DLTVerificationMixin:
    """
    Mixin class to add DLT verification to TestBase subclasses.
    
    Usage:
        class MyTest(DLTVerificationMixin, TestBase):
            pass
    
    The mixin provides:
    - save_dlt_file(): Save DLT to versioned directory
    - verify_dlt_logs(): Run verification
    - get_dlt_summary(): Get results summary
    - get_test_report(): Get comprehensive report
    """
    
    def save_dlt_file(
        self,
        source_dlt_path: str,
        test_name: str = "basic_sanity",
        base_path: str = "logs/sanity"
    ) -> bool:
        """
        Save DLT file to versioned directory based on device version.
        
        Args:
            source_dlt_path: Path to source DLT file
            test_name: Test name for filename (default: "basic_sanity")
            base_path: Base path for versioned logs
        
        Returns:
            True if saved successfully
        """
        if not hasattr(self, '_dlt_helper') or self._dlt_helper is None:
            # Create helper if not exists
            self._dlt_helper = TestBaseDLTHelper(
                version_output=self.config.version_output,
                logger=self.logger,
                base_path=base_path
            )
        
        return self._dlt_helper.save_dlt_file(source_dlt_path, test_name)
    
    def verify_dlt_logs(
        self,
        base_path: str = r"D:\SANITY",
        cleanup: bool = True
    ) -> bool:
        """
        Verify DLT logs using device version from test config.
        
        Args:
            base_path: Base path for organized DLT logs
            cleanup: If True, clean up temporary files
        
        Returns:
            True if all tests passed
        """
        if not hasattr(self, 'config') or not hasattr(self, 'logger'):
            raise RuntimeError(
                "DLTVerificationMixin requires TestBase parent class with "
                "self.config and self.logger"
            )
        
        # Create helper and store for later reference
        if not hasattr(self, '_dlt_helper'):
            self._dlt_helper = None
        
        self._dlt_helper = TestBaseDLTHelper(
            version_output=self.config.version_output,
            logger=self.logger,
            base_path=base_path,
            cleanup_csv=cleanup
        )
        
        return self._dlt_helper.verify()
    
    def get_dlt_summary(self) -> str:
        """Get summary of DLT verification results."""
        if not hasattr(self, '_dlt_helper') or self._dlt_helper is None:
            return "DLT verification not run"
        
        return self._dlt_helper.get_summary()
    
    def get_test_report(self) -> str:
        """
        Get comprehensive test and DLT verification report.
        
        Returns:
            Formatted report string
        """
        if not hasattr(self, '_dlt_helper') or self._dlt_helper is None:
            return "No test report available"
        
        return self._dlt_helper.get_comprehensive_report()


# Example usage pattern
EXAMPLE_TEST_CLASS = '''
#!/usr/bin/env python3
"""
Example: Using DLT verification in basic_sanity test
"""

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_base import TestBase
from dlt.testbase_integration import DLTVerificationMixin


class BasicSanityTest(DLTVerificationMixin, TestBase):
    """V2X Basic Sanity test with automatic DLT verification."""
    
    def get_commands(self):
        """Get test commands."""
        return [
            "sldd v2xmgr setdataprivacy 1",
            ("sldd power requestset 2004 7", 3),
            "sldd v2xmgr setdataprivacy 0",
        ]
    
    def setup_custom(self):
        """Test-specific setup."""
        self.logger.log("Basic sanity test setup complete")
    
    def teardown_custom(self):
        """Test-specific teardown with DLT verification."""
        self.logger.log("\\nRunning post-test DLT verification...")
        
        # Automatically verify DLT logs using device version
        success = self.verify_dlt_logs(
            base_path="logs/sanity",
            cleanup=True  # Auto-cleanup temporary CSV
        )
        
        # Log results
        self.logger.log(self.get_dlt_summary())
        
        if not success:
            self.logger.log_error("DLT verification failed")


if __name__ == "__main__":
    # Run test with automatic DLT verification
    test = BasicSanityTest(
        test_name="basic_sanity",
        log_file="logs/basic_sanity.log"
    )
    
    success = test.run()
    sys.exit(0 if success else 1)
'''


if __name__ == "__main__":
    print("TestBase DLT Integration Module")
    print("="*70)
    print(EXAMPLE_TEST_CLASS)

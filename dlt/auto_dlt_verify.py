#!/usr/bin/env python3
"""
Auto-DLT Verification System
Fully automated end-to-end workflow for DLT verification

Features:
- Auto-detect device version (from test_base.py or device shell command)
- Auto-discover DLT files in versioned directories
- Auto-convert DLT to CSV (temporary)
- Run verification
- Auto-cleanup temporary CSV files

Usage (Standalone):
    python auto_dlt_verify.py [--base-path "D:\\SANITY"]
    
Usage (From test_base.py):
    from auto_dlt_verify import AutoDLTVerifier
    verifier = AutoDLTVerifier(version_output=self.config.version_output, logger=self.logger)
    verifier.verify()

Examples:
    # Standalone with device command
    python auto_dlt_verify.py
    
    # With custom base path
    python auto_dlt_verify.py --base-path "D:\\SANITY"
    
    # Test version override
    python auto_dlt_verify.py --version "v040.040.065.iconsf25.oem_260525"
"""

import sys
import json
import subprocess
import tempfile
import shutil
import argparse
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dlt.dlt_verifier import DLTVerifier
from dlt.version_parser import VersionParser


class AutoDLTVerifier:
    """Fully automated DLT verification workflow."""
    
    def __init__(
        self, 
        version_output: Optional[str] = None,
        logger: Optional[Any] = None,
        base_path: str = "logs/sanity"
    ):
        """
        Initialize auto-verifier.
        
        Args:
            version_output: Device version string (from test_base or device)
            logger: Optional logger instance (from test_base)
            base_path: Base path for organized DLT logs
        """
        self.version_output = version_output
        self.logger = logger
        self.base_path = base_path
        self.temp_csv = None
        self.version_parser = None
        self.dlt_file = None
        self.csv_file = None
        self.results = None
        
        self._log("Initializing AutoDLTVerifier...")
        
        # Parse version
        if self.version_output:
            self.version_parser = VersionParser(self.version_output.strip())
            self._log(f"Version: {self.version_output}")
    
    def _log(self, message: str) -> None:
        """Log message to logger or stdout."""
        if self.logger:
            self.logger.log(message)
        else:
            print(f"[AutoDLTVerify] {message}")
    
    def _log_error(self, message: str) -> None:
        """Log error message."""
        if self.logger:
            self.logger.log_error(message)
        else:
            print(f"❌ [AutoDLTVerify] {message}")
    
    def _log_success(self, message: str) -> None:
        """Log success message."""
        if self.logger:
            self.logger.log(f"✓ {message}")
        else:
            print(f"✓ {message}")
    
    def _prompt_user(self, prompt_text: str, default: Optional[str] = None) -> str:
        """
        Prompt user for input.
        
        Args:
            prompt_text: Question to ask user
            default: Default value if user just presses Enter
        
        Returns:
            User input or default
        """
        if default:
            full_prompt = f"{prompt_text} [{default}]: "
        else:
            full_prompt = f"{prompt_text}: "
        
        try:
            user_input = input(full_prompt).strip()
            if user_input:
                return user_input
            elif default:
                return default
            else:
                return ""
        except (KeyboardInterrupt, EOFError):
            self._log_error("User cancelled input")
            return ""
    
    def _prompt_for_dlt_file(self) -> Optional[Path]:
        """
        Prompt user to manually input DLT file path.
        
        Returns:
            Path to DLT file or None
        """
        print("\n" + "="*70)
        print("DLT FILE NOT FOUND - MANUAL INPUT")
        print("="*70)
        print("\nPlease provide the path to your DLT file.")
        print("Examples:")
        print("  D:\\path\\to\\basic_sanity.dlt")
        print("  logs\\sanity\\260525\\iconsf25\\basic_sanity_v040.040.065.iconsf25.oem_260525.dlt")
        print("  C:\\Users\\user\\Downloads\\dlt_log.dlt")
        print("")
        
        while True:
            dlt_path = self._prompt_user("full path to .dlt file", default=None)
            
            if not dlt_path:
                self._log_error("No path provided")
                return None
            
            dlt_path = Path(dlt_path)
            
            if not dlt_path.exists():
                self._log_error(f"File not found: {dlt_path}")
                retry = self._prompt_user("Try another path? (y/n)", "y")
                if retry.lower() != "y":
                    return None
                continue
            
            if not dlt_path.suffix.lower() == ".dlt":
                self._log_error(f"File is not a .dlt file: {dlt_path}")
                retry = self._prompt_user("Try another file? (y/n)", "y")
                if retry.lower() != "y":
                    return None
                continue
            
            self._log_success(f"Selected DLT file: {dlt_path}")
            return dlt_path
    
    def _prompt_for_version(self) -> Optional[str]:
        """
        Prompt user to manually input device version.
        
        Returns:
            Version string or None
        """
        print("\n" + "="*70)
        print("DEVICE VERSION NOT DETECTED - MANUAL INPUT")
        print("="*70)
        print("\nPlease provide the device version.")
        print("Expected format: v{major}.{minor}.{patch}.{variant}.oem_{date}")
        print("Examples:")
        print("  v040.040.065.iconsf25.oem_260525")
        print("  v1.2.3.icon25.oem_250101")
        print("")
        
        while True:
            version = self._prompt_user("device version", default=None)
            
            if not version:
                self._log_error("Version required")
                return None
            
            # Basic validation - should contain "v" and "oem_"
            if not version.startswith("v") or "oem_" not in version:
                self._log_error(
                    f"Invalid format: {version}\n"
                    "Expected: v{{major}}.{{minor}}.{{patch}}.{{variant}}.oem_{{date}}"
                )
                retry = self._prompt_user("Try again? (y/n)", "y")
                if retry.lower() != "y":
                    return None
                continue
            
            self._log_success(f"Device version: {version}")
            return version
    
    def get_device_version(self) -> Optional[str]:
        """
        Get device version from 'cat /etc/version' command.
        
        Returns:
            Version string or None
        """
        try:
            # Try using ADB shell
            result = subprocess.run(
                ["adb", "shell", "cat", "/etc/version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            self._log_error(f"Failed to get device version: {e}")
        
        return None
    
    def discover_dlt(self, allow_user_input: bool = True) -> Optional[Path]:
        """
        Auto-discover DLT file in versioned directory.
        
        Prefers the clean version file (without ICON_NAD prefix).
        If not found, optionally prompt user for manual input.
        
        Args:
            allow_user_input: If True and DLT not found, prompt user
        
        Returns:
            Path to DLT file or None
        """
        if not self.version_parser or not self.version_parser.full_version:
            self._log_error("No valid version to search for")
            return None
        
        version_dir = self.version_parser.get_directory_path(self.base_path)
        
        if not version_dir.exists():
            self._log_error(f"Version directory not found: {version_dir}")
        else:
            # Try exact filename with clean version first
            expected_dlt = version_dir / self.version_parser.get_expected_dlt_filename()
            if expected_dlt.exists():
                self._log_success(f"Found DLT file: {expected_dlt}")
                return expected_dlt
            
            # Try any basic_sanity_*.dlt but prefer clean version (no ICON_NAD prefix)
            dlt_files = list(version_dir.glob("basic_sanity_*.dlt"))
            if dlt_files:
                # Prefer files without device-specific prefixes
                for dlt_file in dlt_files:
                    if "ICON_NAD" not in dlt_file.name and "ICON25SF" not in dlt_file.name:
                        self._log_success(f"Found DLT file: {dlt_file}")
                        return dlt_file
                
                # Fallback: use any available file
                self._log_success(f"Found DLT file: {dlt_files[0]}")
                return dlt_files[0]
        
        # Not found - ask user
        if allow_user_input:
            self._log_error(f"No DLT files found in: {version_dir}")
            user_dlt = self._prompt_for_dlt_file()
            if user_dlt:
                return user_dlt
        else:
            self._log_error(f"No DLT files found in: {version_dir}")
        
        return None
    
    def convert_dlt_to_csv(self, dlt_file: Path) -> Optional[Path]:
        """
        Convert DLT file to CSV using dlt-viewer.exe CLI.
        
        Uses dlt-viewer in silent/headless mode to convert DLT to CSV format.
        
        Args:
            dlt_file: Path to DLT file
        
        Returns:
            Path to CSV file (temporary) or None
        """
        if not dlt_file.exists():
            self._log_error(f"DLT file not found: {dlt_file}")
            return None
        
        # Create temporary CSV
        self.temp_csv = Path(tempfile.gettempdir()) / f"dlt_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        self._log(f"Converting DLT to CSV (temp): {self.temp_csv}")
        
        # Method 1: Use dlt-viewer.exe from SDK with explicit path
        dlt_viewer_path = Path(__file__).resolve().parent / "DltViewerSDK-2.21.3" / "dlt-viewer.exe"
        
        if dlt_viewer_path.exists():
            try:
                # Silent/headless mode: -e for export, -o for output, -f for format
                result = subprocess.run(
                    [str(dlt_viewer_path), "-e", str(dlt_file), "-o", str(self.temp_csv), "-f", "csv"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and self.temp_csv.exists():
                    file_size = self.temp_csv.stat().st_size
                    if file_size > 0:
                        self._log_success(f"DLT converted to CSV ({file_size} bytes)")
                        return self.temp_csv
                else:
                    self._log(f"dlt-viewer.exe returned code {result.returncode}")
                    if result.stderr:
                        self._log(f"  stderr: {result.stderr[:200]}")
            except Exception as e:
                self._log(f"dlt-viewer.exe method failed: {e}")
        else:
            self._log(f"dlt-viewer.exe not found at: {dlt_viewer_path}")
        
        # Method 2: Try system dlt-viewer if available
        try:
            result = subprocess.run(
                ["dlt-viewer", "-e", str(dlt_file), "-o", str(self.temp_csv), "-f", "csv"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and self.temp_csv.exists():
                file_size = self.temp_csv.stat().st_size
                if file_size > 0:
                    self._log_success(f"DLT converted to CSV ({file_size} bytes)")
                    return self.temp_csv
        except Exception as e:
            self._log(f"System dlt-viewer method failed: {e}")
        
        # Method 3: Try DLT SDK extraction tools
        try:
            result = self._extract_csv_from_dlt(dlt_file, self.temp_csv)
            if result:
                return self.temp_csv
        except Exception as e:
            self._log(f"DLT extraction method failed: {e}")
        
        self._log_error("Failed to convert DLT to CSV using all available methods")
        return None
    
    def _extract_csv_from_dlt(self, dlt_file: Path, csv_file: Path) -> bool:
        """
        Extract CSV from DLT using SDK or binary tools.
        
        Args:
            dlt_file: Input DLT file
            csv_file: Output CSV file
        
        Returns:
            True if successful
        """
        # Look for DLT converter tools in the workspace
        converters = [
            Path(__file__).parent / "DltViewerSDK-2.21.3" / "bin" / "dlt_convert.exe",
            Path(__file__).parent / "DltViewerSDK-2.21.3" / "plugins" / "convert" / "dlt_convert.exe",
        ]
        
        for converter in converters:
            if converter.exists():
                try:
                    result = subprocess.run(
                        [str(converter), "-c", "-o", str(csv_file), str(dlt_file)],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0 and csv_file.exists():
                        return True
                except Exception:
                    continue
        
        return False
    
    def verify_logs(self, csv_file: Path) -> bool:
        """
        Run DLT verification on CSV file.
        
        Args:
            csv_file: Path to CSV file
        
        Returns:
            True if all tests passed
        """
        if not csv_file.exists():
            self._log_error(f"CSV file not found: {csv_file}")
            return False
        
        self._log("Running DLT verification...")
        
        try:
            # Create verifier with version context
            verifier = DLTVerifier(str(csv_file), version=self.version_output)
            
            # Run verification
            self.results = verifier.verify_all(regions=["Universal"])
            
            # Display report
            report = verifier.generate_readable_report(self.results)
            self._log(report)
            
            # Check if all passed
            all_passed = all(r.status == "Pass" for r in self.results.values())
            
            if all_passed:
                self._log_success("All tests PASSED")
            else:
                self._log_error("Some tests FAILED")
                
                # Save JSON report
                json_report = verifier.generate_report(self.version_output, self.results)
                report_file = csv_file.parent / "dlt_verification_results.json"
                
                with open(report_file, "w") as f:
                    json.dump(json_report, f, indent=2)
                
                self._log(f"JSON report saved: {report_file}")
            
            return all_passed
        
        except Exception as e:
            self._log_error(f"Verification failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def cleanup(self) -> None:
        """Clean up temporary files."""
        if self.temp_csv and self.temp_csv.exists():
            try:
                self.temp_csv.unlink()
                self._log_success(f"Cleaned up temporary CSV: {self.temp_csv.name}")
            except Exception as e:
                self._log(f"Failed to delete temp CSV: {e}")
    
    def verify(self) -> bool:
        """
        Run complete verification workflow.
        
        Returns:
            True if all tests passed, False otherwise
        """
        try:
            # Get version if not provided
            if not self.version_output:
                self._log("Getting device version from device...")
                self.version_output = self.get_device_version()
                
                if not self.version_output:
                    self._log_error("Could not determine device version automatically")
                    self.version_output = self._prompt_for_version()
                
                if not self.version_output:
                    self._log_error("No device version available")
                    return False
                
                self.version_parser = VersionParser(self.version_output)
            
            # Discover DLT file (with user input fallback)
            self._log("Discovering DLT file...")
            self.dlt_file = self.discover_dlt(allow_user_input=True)
            
            if not self.dlt_file:
                return False
            
            # Convert to CSV
            self._log("Converting DLT to CSV...")
            self.csv_file = self.convert_dlt_to_csv(self.dlt_file)
            
            if not self.csv_file:
                return False
            
            # Load CSV and verify
            result = self.verify_logs(self.csv_file)
            
            return result
        
        except Exception as e:
            self._log_error(f"Verification workflow failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            # Always cleanup
            self.cleanup()
    
    def get_setup_info(self) -> Dict[str, Any]:
        """Get setup information for this verification run."""
        info = {
            "timestamp": datetime.now().isoformat(),
            "version": self.version_output,
            "dlt_file": str(self.dlt_file) if self.dlt_file else None,
            "csv_file": str(self.csv_file) if self.csv_file else None,
            "base_path": self.base_path,
            "results": self.results,
        }
        
        if self.version_parser:
            info["date"] = self.version_parser.date
            info["variant"] = self.version_parser.device_variant
        
        return info


def main():
    """Main entry point for standalone execution."""
    parser = argparse.ArgumentParser(
        description="Automated DLT Verification Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
WORKFLOW:

1. Detects device version (from device or argument)
2. Discovers DLT file in versioned directory
3. Converts DLT to CSV (temporary)
4. Runs verification
5. Cleans up temporary files
6. Returns pass/fail status

EXAMPLES:

Auto-detect everything:
  python auto_dlt_verify.py
  
With custom base path:
  python auto_dlt_verify.py --base-path "D:\SANITY"
  
Override version:
  python auto_dlt_verify.py --version "v040.040.065.iconsf25.oem_260525"

CHECK RESULTS:
  Results saved to: {version_dir}/dlt_verification_results.json
        """
    )
    
    parser.add_argument(
        "--base-path",
        default="logs/sanity",
        help="Base path for versioned DLT logs (default: logs/sanity)"
    )
    
    parser.add_argument(
        "--version",
        help="Override device version string"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("AUTOMATED DLT VERIFICATION")
    print("="*70 + "\n")
    
    # Create verifier
    verifier = AutoDLTVerifier(
        version_output=args.version,
        base_path=args.base_path
    )
    
    # Run verification
    success = verifier.verify()
    
    # Print setup info
    print("\n" + "="*70)
    print("VERIFICATION INFO")
    print("="*70)
    
    info = verifier.get_setup_info()
    print(json.dumps(info, indent=2, default=str))
    
    print("="*70 + "\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
